import autogen
from dotenv import load_dotenv
import os
import random

# environment variables
load_dotenv()

# API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file")

# LLM Config
config_list = [
    {
        "model": "gemini-2.5-flash",
        "api_key": api_key,
        "api_type": "google"
    }
]
llm_config = {
    "cache_seed": 42,
    "temperature": 0.7,
    "config_list": config_list,
    "timeout": 120,
}

# Environment Settings
CAPACITY = 100  # Max students per batch to avoid congestion
ATTENDANCES = {"C1": 50, "C2": 60, "C3": 70}  # Per classroom
SLOTS = [-4, -2, 0, 2, 4]  # Available shift minutes for batches (2 min apart)
NUM_WEEKS = 1  # Number of weeks to simulate
CLASS_DURATION = 60  # Assume 1-hour class duration in minutes

# Weekly Timetable
TIMETABLE = {
    "Monday": ["9:00", "10:00", "11:00"],  # Back-to-back classes in morning
    "Tuesday": ["9:00", "11:00", "14:00"],
    "Wednesday": ["9:00", "10:00", "11:00"],  # Back-to-back classes again
    "Thursday": ["9:00", "11:00", "14:00"],
    "Friday": ["9:00", "10:00", "14:00"]  # 9:00 and 10:00 are back-to-back
}

# Persistent State
commitment_history = {}  # (debtor, creditor, slot_day): minutes owed
reward_scores = {"C1": 0, "C2": 0, "C3": 0}  # Reward points
violation_counts = {"C1": 0, "C2": 0, "C3": 0}  # Violation counts per agent

# Function to update system messages with current state
def get_b_system_message(estimated_total):
    return f"""
You are Agent B, monitoring the bottleneck. Start by broadcasting:
- Current capacity: {CAPACITY} students per 2-minute batch.
- Estimated total students: {estimated_total}.
- Classes last 1 hour, so consider congestion from both exiting students and incoming students for the next class.
Then, observe and remind agents if congestion is likely to happen, especially with overlapping class ends and starts. Do not negotiate.
"""

def get_c_system_message(name, attendance):
    history_str = "\nCurrent commitments:\n"
    for (debtor, creditor, slot_day), mins in commitment_history.items():
        history_str += f"{debtor} owes {creditor} {mins} minutes for {slot_day}.\n"
    
    reward = reward_scores[name]
    violations = violation_counts[name]
    
    return f"""
You are Classroom Agent {name} with {attendance} students attending.
Your goal is to negotiate with other classroom agents to stagger exit times and avoid congestion, considering 1-hour classes and overlapping traffic from incoming students.
- First, honor existing commitments if any. Refuse with probability based on reward (20% if reward > 5, 50% otherwise).
- Your current reward score: {reward} (increases by 2 for honoring, decreases by 2 for refusing).
- Your violation count: {violations} (if >3, raise violation event).
- Propose commitments like: 'If you finish some minutes early (e.g., 2 minutes), I'll finish on time; in return, next time you get extra time.'
- Accept proposals with probability: 80% if reward > 5, 50% otherwise; refuse with 20% chance for complex topics.
- After a deal, broadcast the revised exit slot and shifted students (e.g., '{name} shifting to -2 min with {attendance} students').
- Aim for batches <= {CAPACITY} students, accounting for potential overlap with next slot's arrivals within the 1-hour window.
- Available slots: {SLOTS} minutes from scheduled end (adjusted around 1-hour class end).
- Be cooperative but autonomous.{history_str}
"""

# User Proxy Agent to initiate chat
user_proxy = autogen.UserProxyAgent(
    name="Admin",
    human_input_mode="NEVER",
    code_execution_config=False,
)

# Speaker selection: Round-robin to avoid race conditions
def round_robin_speaker(last_speaker, groupchat):
    agents = groupchat.agents
    if last_speaker is None or last_speaker not in agents:
        return groupchat.agents[0]  # Start with B
    current_idx = agents.index(last_speaker)
    next_idx = (current_idx + 1) % len(agents)
    return agents[next_idx]

# Simulate for each week and slot
for week in range(1, NUM_WEEKS + 1):
    for day, slots in TIMETABLE.items():
        for i, slot in enumerate(slots):
            # Estimate total students, adding variability for incoming students from next slot if consecutive
            estimated_total = sum(ATTENDANCES.values())
            if i + 1 < len(slots) and int(slots[i + 1].split(":")[0]) - int(slot.split(":")[0]) == 1:
                estimated_total += random.randint(0, 50)  # Simulate incoming students
            print(f"\n=== Week {week}, {day} {slot} Slot ===\n")
            
            # Create/Recreate Agents with updated system messages
            b_agent = autogen.AssistantAgent(
                name="B",
                system_message=get_b_system_message(estimated_total),
                llm_config=llm_config,
            )
            
            c1_agent = autogen.AssistantAgent(
                name="C1",
                system_message=get_c_system_message("C1", ATTENDANCES["C1"]),
                llm_config=llm_config,
            )
            
            c2_agent = autogen.AssistantAgent(
                name="C2",
                system_message=get_c_system_message("C2", ATTENDANCES["C2"]),
                llm_config=llm_config,
            )
            
            c3_agent = autogen.AssistantAgent(
                name="C3",
                system_message=get_c_system_message("C3", ATTENDANCES["C3"]),
                llm_config=llm_config,
            )
            
            # Group Chat Setup
            groupchat = autogen.GroupChat(
                agents=[b_agent, c1_agent, c2_agent, c3_agent],
                messages=[],
                max_round=12,
                speaker_selection_method=round_robin_speaker,
            )
            
            # Group Chat Manager
            manager = autogen.GroupChatManager(
                groupchat=groupchat,
                llm_config=llm_config,
            )
            
            # Initiate the Simulation
            user_proxy.initiate_chat(
                manager,
                message=f"Start the simulation for Week {week}, {day} {slot} slot. Coordinate to avoid congestion, honor commitments, and use rewards/probabilities. Consider overlaps from consecutive 1-hour classes.",
            )
            
            # Post-simulation: Update state based on negotiation (simulated)
            slot_day = f"{slot} {day}"
            if random.random() > 0.5:  # Simulate a new commitment
                debtor, creditor = random.choice(["C1", "C2", "C3"]), random.choice(["C1", "C2", "C3"])
                if debtor != creditor:
                    mins = random.choice([2, 4])
                    commitment_history[(debtor, creditor, slot_day)] = commitment_history.get((debtor, creditor, slot_day), 0) + mins
                    reward_scores[debtor] -= 1
                    reward_scores[creditor] += 1
                    print(f"New commitment: {debtor} owes {creditor} {mins} min for {slot_day}.")
            
            if random.random() < 0.2:  # Simulate refusal
                agent = random.choice(["C1", "C2", "C3"])
                violation_counts[agent] += 1
                reward_scores[agent] -= 2
                if violation_counts[agent] > 3:
                    print(f"Violation event raised for {agent} at {slot_day}!")
            
            if random.random() > 0.7 and commitment_history:  # Simulate honoring
                key = random.choice(list(commitment_history.keys()))
                if key[2] == slot_day:  # Honor if relevant to current slot
                    del commitment_history[key]
                    reward_scores[key[0]] += 2
                    print(f"Honored commitment: {key[0]} cleared debt to {key[1]} for {slot_day}.")

print("\n=== Simulations Complete. Check console for negotiated exits and state updates. ===")