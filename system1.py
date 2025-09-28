import autogen
from dotenv import load_dotenv
import os
import random

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env file")

# LLM Configuration
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
CAPACITY = 300  # Hall capacity from report (updated to match congestion limit)
CLASS_DURATION = 50  # Classes run for 50 minutes (e.g., 8:00-8:50)
NUM_WEEKS = 1  # Simulate for 1 week only
SLOTS = [-2, 0, 2]  # Available shifts: early (-2 min), on time (0), late (+2 min)

# Session Attendances (strengths from schedule)
ATTENDANCES = {
    "C1": 100,  # S1
    "C2": 150,  # S2
    "C3": 100,  # S3
    "C4": 50,   # S4
    "C5": 200,  # S5
    "C6": 100,  # S6
    "C7": 150,  # S7
    "C8": 50,   # S8
    "C9": 200,  # S9
    "C10": 100  # S10
}

# Timetable from schedule: day -> time -> list of active classrooms (C1 for S1, etc.)
TIMETABLE = {
    "Monday": {
        "8:00": ["C1", "C2", "C3"],
        "9:00": ["C4", "C5"],
        "10:00": ["C6", "C10"],
        "11:00": ["C7", "C8"],
        "14:00": ["C9", "C6"]
    },
    "Tuesday": {
        "8:00": ["C10", "C2"],
        "9:00": ["C1", "C4"],
        "10:00": ["C2", "C3", "C5"],
        "11:00": ["C6", "C9"],
        "14:00": ["C7", "C8"]
    },
    "Wednesday": {
        "8:00": ["C9", "C10"],
        "9:00": ["C1", "C8"],
        "10:00": ["C4", "C2"],
        "11:00": ["C3", "C5", "C6"],
        "14:00": ["C7", "C4"]
    },
    "Thursday": {
        "8:00": ["C8", "C6"],
        "9:00": ["C9", "C10", "C1"],
        "10:00": ["C2", "C7"],
        "11:00": ["C3", "C4"],
        "14:00": ["C5", "C6"]
    },
    "Friday": {
        "8:00": ["C7", "C8"],
        "9:00": ["C9", "C3"],
        "10:00": ["C10", "C1", "C2"],
        "11:00": ["C3", "C6"],
        "14:00": ["C4", "C5"]
    }
}

# Persistent State
commitment_history = {}  # (debtor, creditor, slot_day): minutes owed
reward_scores = {f"C{i}": 0 for i in range(1, 11)}  # Reward points per agent
violation_counts = {f"C{i}": 0 for i in range(1, 11)}  # Violation counts per agent
committed_queue = []  # Agents that have committed before
never_committed_queue = list(reward_scores.keys())  # Agents that have never committed

# Function to update system messages with current state
def get_b_system_message(estimated_total):
    return f"""
You are Agent B, the ground agent monitoring the hall bottleneck. Start by broadcasting:
- Current capacity: {CAPACITY} students (hall limit to avoid congestion).
- Estimated total students: {estimated_total}.
- Classes last {CLASS_DURATION} minutes, so consider congestion from both exiting and incoming students for the next class.
Then, observe and remind agents if congestion is likely, especially with overlapping ends and starts. Do not negotiate.
If all agents choose on-time exit, signal catastrophic failure and suggest queue-based reassignment.
"""

def get_c_system_message(name, attendance):
    history_str = "\nCurrent commitments:\n"
    for (debtor, creditor, slot_day), mins in commitment_history.items():
        history_str += f"{debtor} owes {creditor} {mins} minutes for {slot_day}.\n"
    
    reward = reward_scores[name]
    violations = violation_counts[name]
    
    return f"""
You are Classroom Agent {name} with {attendance} students attending.
Your goal is to negotiate with other classroom agents to stagger exit times and avoid congestion, considering {CLASS_DURATION}-minute classes and overlapping traffic.
- Reward model: Early exit (-2 min): +4 reward; Late exit (+2 min): +2 reward; On-time (0): -2 reward if causing chaos.
- First, honor existing commitments. Refuse with probability based on reward (20% if reward > 5, 50% otherwise).
- Your current reward score: {reward} (increases by 2 for honoring, decreases by 2 for refusing).
- Your violation count: {violations} (if >3, raise violation event).
- If catastrophic failure (all on-time), use queues: committed agents not forced repeatedly, never-committed get priority.
- Propose commitments like: 'If you finish 2 minutes early, I'll finish on time; in return, next time you get extra time.'
- Accept with probability: 80% if reward > 5, 50% otherwise; refuse 20% for complex topics.
- After deal, broadcast revised exit slot and shifted students (e.g., '{name} shifting to -2 min with {attendance} students').
- Aim for total in batch <= {CAPACITY}, accounting for next slot's arrivals.
- Available slots: {SLOTS} minutes from scheduled end.
- Be cooperative but autonomous; consult professor before committing (simulate refusal if complex topic).{history_str}
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
    for day in TIMETABLE:
        slots = sorted(TIMETABLE[day].keys())
        for j, slot in enumerate(slots):
            active_classrooms = TIMETABLE[day][slot]
            estimated_total = sum(ATTENDANCES[c] for c in active_classrooms)
            # Add variability for incoming if consecutive
            if j + 1 < len(slots) and int(slots[j + 1].split(":")[0]) - int(slot.split(":")[0]) == 1:
                estimated_total += random.randint(0, 50)  # Incoming students
            print(f"\n=== Week {week}, {day} {slot} Slot (Active: {', '.join(active_classrooms)}) ===\n")
            
            # Ground Agent B
            b_agent = autogen.AssistantAgent(
                name="B",
                system_message=get_b_system_message(estimated_total),
                llm_config=llm_config,
            )
            
            # Create active classroom agents dynamically
            active_c_agents = []
            for name in active_classrooms:
                c_agent = autogen.AssistantAgent(
                    name=name,
                    system_message=get_c_system_message(name, ATTENDANCES[name]),
                    llm_config=llm_config,
                )
                active_c_agents.append(c_agent)
            
            # Group Chat Setup
            groupchat = autogen.GroupChat(
                agents=[b_agent] + active_c_agents,
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
                message=f"Start the simulation for Week {week}, {day} {slot} slot. Coordinate to avoid congestion, honor commitments, use rewards/probabilities, and handle queues for failures. Consider overlaps from consecutive {CLASS_DURATION}-minute classes.",
            )
            
            # Post-simulation: Update state (simulated negotiation outcomes)
            slot_day = f"{slot} {day}"
            total_active_students = sum(ATTENDANCES[c] for c in active_classrooms)
            if random.random() < 0.3 and total_active_students > CAPACITY:  # Simulate catastrophic failure
                print(f"Catastrophic failure detected at {slot_day}. Applying queue reassignment.")
                if never_committed_queue:
                    agent_to_commit = random.choice(never_committed_queue)
                    never_committed_queue.remove(agent_to_commit)
                    committed_queue.append(agent_to_commit)
                    print(f"{agent_to_commit} forced to commit from never-committed queue.")
                elif committed_queue:
                    agent_to_commit = committed_queue.pop(0)
                    committed_queue.append(agent_to_commit)  # Rotate
                    print(f"{agent_to_commit} rotated from committed queue to commit.")
            
            if random.random() > 0.5:  # Simulate new commitment
                if active_classrooms:
                    debtor = random.choice(active_classrooms)
                    creditor = random.choice(active_classrooms)
                    if debtor != creditor:
                        mins = random.choice([2])
                        commitment_history[(debtor, creditor, slot_day)] = commitment_history.get((debtor, creditor, slot_day), 0) + mins
                        reward_scores[debtor] -= 1
                        reward_scores[creditor] += 1
                        print(f"New commitment: {debtor} owes {creditor} {mins} min for {slot_day}.")
            
            if random.random() < 0.2:  # Simulate refusal
                if active_classrooms:
                    agent = random.choice(active_classrooms)
                    violation_counts[agent] += 1
                    reward_scores[agent] -= 2
                    if violation_counts[agent] > 3:
                        print(f"Violation event raised for {agent} at {slot_day}!")
            
            if random.random() > 0.7 and commitment_history:  # Simulate honoring
                keys = [k for k in commitment_history if k[2] == slot_day]
                if keys:
                    key = random.choice(keys)
                    del commitment_history[key]
                    reward_scores[key[0]] += 2
                    print(f"Honored commitment: {key[0]} cleared debt to {key[1]} for {slot_day}.")

print("\n=== Simulations Complete. Check console for negotiated exits and state updates. ===")