import autogen
from dotenv import load_dotenv
import os
import random
import time

# Environment variables
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
BOTTLENECK_CAPACITY = 100  # Pedestrians/cyclists per minute through bottleneck point
CLEARANCE_TIME = 2  # Minutes to clear bottleneck if no congestion
BATCH_SPACING = 2   # Minutes between batches
NUM_WEEKS = 2       # Simulate multiple weeks for commitment tracking

# Classroom Settings
CLASSROOM_ATTENDANCE = {
    "C1": 120,  # High attendance 
    "C2": 80,   # Medium attendance
    "C3": 90,   # Medium attendance
    "C4": 60,   # Low attendance
    "C5": 100   # High attendance
}

# Weekly Timetable
TIMETABLE = {
    "Monday": {
        "11:00": ["C1", "C2", "C3"],  # 290 students - high coordination
        "10:00": ["C4", "C5"]         # 160 students - moderate coordination
    },
    "Tuesday": {
        "11:00": ["C1", "C4"],       # 180 students - moderate coordination
        "10:00": ["C2", "C3", "C5"]  # 270 students - needs coordination
    },
    "Wednesday": {
        "11:00": ["C2", "C3", "C4", "C5"],  # 330 students - very high coordination
    }
}

# Global States
class SystemState:
    def __init__(self):
        self.commitments = {}  # (debtor, creditor, day, slot): {"minutes": X, "week_made": Y, "fulfilled": False}
        self.violations = {f"C{i}": 0 for i in range(1, 6)}
        self.current_bottleneck_flow = BOTTLENECK_CAPACITY
        self.students_in_transit = 0
        self.week_number = 1
        
    def add_commitment(self, debtor, creditor, day, slot, minutes):
        key = (debtor, creditor, day, slot)
        self.commitments[key] = {
            "minutes": minutes,
            "week_made": self.week_number,
            "fulfilled": False
        }
        
    def get_pending_commitments(self, agent, day, slot):
        """Get commitments this agent needs to fulfill"""
        pending = []
        for (debtor, creditor, c_day, c_slot), details in self.commitments.items():
            if debtor == agent and c_day == day and c_slot == slot and not details["fulfilled"]:
                pending.append((creditor, details["minutes"]))
        return pending
        
    def fulfill_commitment(self, debtor, creditor, day, slot):
        key = (debtor, creditor, day, slot)
        if key in self.commitments:
            self.commitments[key]["fulfilled"] = True
            return True
        return False
        
    def record_violation(self, agent):
        self.violations[agent] += 1
        return self.violations[agent] > 3
        
    def update_bottleneck_status(self, current_students):
        """Simulate dynamic bottleneck capacity based on current traffic"""
        if current_students > BOTTLENECK_CAPACITY:
            self.current_bottleneck_flow = max(50, BOTTLENECK_CAPACITY - 20)  # Reduced capacity
        else:
            self.current_bottleneck_flow = BOTTLENECK_CAPACITY
        self.students_in_transit = current_students


system_state = SystemState()

def get_agent_b_system_message(active_classrooms, total_students):
    """Agent B monitors the road bottleneck point"""
    congestion_status = "CRITICAL" if total_students > BOTTLENECK_CAPACITY else "NORMAL"
    
    return f"""
You are Agent B - the ROAD BOTTLENECK MONITOR.
You observe the narrow road leading to the lecture hall complex.

CURRENT SITUATION:
- Bottleneck capacity: {system_state.current_bottleneck_flow} pedestrians/cyclists per minute
- Active classrooms ending now: {active_classrooms}
- Estimated total students: {total_students}
- Students currently in transit: {system_state.students_in_transit}
- Congestion status: {congestion_status}

YOUR RESPONSIBILITIES:
1. Monitor the bottleneck point traffic flow in real-time
2. Broadcast current traffic handling capacity to classroom agents
3. Alert when congestion is likely to happen (total > {BOTTLENECK_CAPACITY}/min)
4. Track student flow rates and clearance times
5. Do NOT negotiate - only observe and inform

MESSAGING FORMAT:
- Start with: "BOTTLENECK STATUS: Current capacity {system_state.current_bottleneck_flow}/min, Total incoming: {total_students} students"
- If congestion likely: "CONGESTION ALERT: Incoming traffic exceeds bottleneck capacity! Coordination required."
- Provide updates: "Traffic flow update: [describe current bottleneck conditions]"

Remember: Students need {CLEARANCE_TIME} minutes to clear bottleneck if no congestion occurs.
With {total_students} students and {BOTTLENECK_CAPACITY}/min capacity, coordination is {'CRITICAL' if total_students > BOTTLENECK_CAPACITY else 'RECOMMENDED'}.
"""

def get_classroom_agent_system_message(classroom, active_classrooms, day, slot):
    """Classroom agent with professor consultation capability"""
    
    attendance = CLASSROOM_ATTENDANCE[classroom]
    
    # Get pending commitments
    pending = system_state.get_pending_commitments(classroom, day, slot)
    violations = system_state.violations[classroom]
    
    # Professor personality
    professor_type = random.choice(["flexible", "strict", "time_conscious"])
    
    commitment_str = ""
    if pending:
        commitment_str = f"\nPENDING COMMITMENTS TO FULFILL:\n"
        for creditor, minutes in pending:
            commitment_str += f"- Owe {creditor} {minutes} minutes adjustment\n"
    
    other_classrooms = [c for c in active_classrooms if c != classroom]
    
    return f"""
You are Classroom Agent {classroom}.
Students in your class: {attendance}
Professor type: {professor_type}
Current violations: {violations}/3

SITUATION AWARENESS:
1. Day: {day}, Time slot: {slot}
2. Other active classrooms: {other_classrooms}
3. You must consult with your professor before making commitments

NEGOTIATION CAPABILITIES:
1. MAKE COMMITMENTS: "If you finish 2 minutes early, I'll continue till scheduled time. Next {day} {slot}, I owe you 2 extra minutes."
2. COUNTER-COMMITMENTS: If professor has complex topic: "I cannot finish early, but can extend. How about you take 2 minutes early, I'll take 2 minutes late?"
3. FULFILL COMMITMENTS: Honor previous promises or risk violations

PROFESSOR CONSULTATION RESULTS:
1. Flexible professor: Usually accepts time adjustments (80% chance)
2. Strict professor: Reluctant for early finish (30% chance), may extend (60% chance)  
3. Time_conscious professor: Prefers on-time finish (90% chance), rarely extends (20% chance)

BATCH CREATION RULES:
1. If attendance > {BOTTLENECK_CAPACITY}, create multiple batches
2. Batch spacing: {BATCH_SPACING} minutes apart
3. Available slots: -4, -2, 0, +2, +4 minutes from scheduled end
4. Broadcast format: "{classroom} creating batch at [time] with [X] students"

COMMITMENT PROTOCOL:
1. Proposal: "I propose [classroom] finishes [timing]. In return, next {day} {slot}, you get [benefit]"
2. Acceptance: "Professor consulted. Agreed to [terms] with [agent]"
3. Counter: "Professor says complex topic today. Counter-propose: [alternative]"
4. Broadcast success: "{classroom} shifts {attendance} students to [time slot]"

CONSTRAINTS:
1. Must honor existing commitments or face violations
2. Professor consultation affects your flexibility
3. Aim to avoid bottleneck congestion

{commitment_str}

Start by stating your attendance and any pending commitments, then engage in negotiation.
"""

def calculate_batches_needed(attendance):
    """Calculate how many batches needed based on bottleneck capacity"""
    return max(1, (attendance + BOTTLENECK_CAPACITY - 1) // BOTTLENECK_CAPACITY)

def simulate_professor_decision(classroom, proposal_type):
    """Simulate professor's decision on time adjustments"""
    professor_types = ["flexible", "strict", "time_conscious"]
    prof_type = random.choice(professor_types)
    
    if prof_type == "flexible":
        return random.random() < 0.8
    elif prof_type == "strict":
        return random.random() < 0.4
    else:  # time_conscious
        return random.random() < 0.3

# User Proxy Agent
user_proxy = autogen.UserProxyAgent(
    name="Admin",
    human_input_mode="NEVER",
    code_execution_config=False,
)

def custom_speaker_selection(last_speaker, groupchat):
    """Custom speaker selection to ensure proper flow"""
    agents = groupchat.agents
    
    # Always start with Agent B for status update
    if last_speaker is None:
        return next((agent for agent in agents if agent.name == "B"), agents[0])
    
    # After B, go through classroom agents
    if last_speaker.name == "B":
        classroom_agents = [agent for agent in agents if agent.name != "B"]
        return classroom_agents[0] if classroom_agents else agents[0]
    
    # Occasionally go back to B for status updates
    if random.random() < 0.2:  # 20% chance
        return next((agent for agent in agents if agent.name == "B"), agents[0])
    
    # Otherwise, continue round-robin
    try:
        current_idx = agents.index(last_speaker)
        next_idx = (current_idx + 1) % len(agents)
        return agents[next_idx]
    except:
        return agents[0]

# Main Simulation
def run_simulation():
    print("Multiagent Road Bottleneck Coordination System Started")
    
    for week in range(1, NUM_WEEKS + 1):
        system_state.week_number = week
        print(f"\nWEEK {week}")
        
        for day, schedule in TIMETABLE.items():
            for time_slot, active_classrooms in schedule.items():
                
                # Calculate total students
                total_students = sum(CLASSROOM_ATTENDANCE[classroom] for classroom in active_classrooms)
                
                print(f"\nSimulation: {day} {time_slot}")
                print(f"Active Classrooms: {active_classrooms}")
                print(f"Individual Attendance: {[f'{c}({CLASSROOM_ATTENDANCE[c]})' for c in active_classrooms]}")
                print(f"Total Students: {total_students}")
                print(f"Bottleneck Capacity: {BOTTLENECK_CAPACITY}/min")
                
                # Update bottleneck status
                system_state.update_bottleneck_status(total_students)
                
                # Create Agent B
                agent_b = autogen.AssistantAgent(
                    name="B",
                    system_message=get_agent_b_system_message(active_classrooms, total_students),
                    llm_config=llm_config,
                )
                
                # Create Classroom Agents
                classroom_agents = []
                for classroom in active_classrooms:
                    agent = autogen.AssistantAgent(
                        name=classroom,
                        system_message=get_classroom_agent_system_message(classroom, active_classrooms, day, time_slot),
                        llm_config=llm_config,
                    )
                    classroom_agents.append(agent)
                
                # Setup Group Chat
                all_agents = [agent_b] + classroom_agents
                groupchat = autogen.GroupChat(
                    agents=all_agents,
                    messages=[],
                    max_round=15,
                    speaker_selection_method=custom_speaker_selection,
                )
                
                manager = autogen.GroupChatManager(
                    groupchat=groupchat,
                    llm_config=llm_config,
                )
                
                # Determine coordination urgency
                if total_students > BOTTLENECK_CAPACITY * 1.5:
                    urgency = "Critical - Multiple batches required"
                    batches_needed = calculate_batches_needed(total_students)
                elif total_students > BOTTLENECK_CAPACITY:
                    urgency = "High - Exit times need to spread out"
                    batches_needed = 2
                else:
                    urgency = "Normal - Not much coordination required"
                    batches_needed = 1
                
                # Start simulation
                initial_message = f"""
Start Bottleneck Coordination Simulation

Scenario: {day} {time_slot} - Week {week}
Urgency Level: {urgency}
Batches Required: {batches_needed}

Status:
1. Road capacity: {system_state.current_bottleneck_flow} pedestrians/min
2. Total students ending classes: {total_students}
3. Classroom breakdown: {', '.join([f'{c}({CLASSROOM_ATTENDANCE[c]})' for c in active_classrooms])}

COORDINATION OBJECTIVES:
1. Agent B: Monitor bottleneck and provide real-time capacity updates
2. Classroom Agents: 
   a. Check for pending commitments from previous weeks
   b. Consult with professors about timing flexibility
   c. Negotiate staggered exit times
   d. Create {BATCH_SPACING}-minute spaced batches if needed
3. Avoid road congestion by keeping flow ≤ {BOTTLENECK_CAPACITY} students/min

Available Time Slots: -4, -2, 0, +2, +4 minutes from scheduled end

Begin Coordination - Agent B start with bottleneck status report
"""
                
                user_proxy.initiate_chat(manager, message=initial_message)
            
                print("\nAfter Simulation State:")
                print("\n \n")
                
                # Simulate commitment outcomes based on negotiation
                for classroom in active_classrooms:
                    # Check commitment fulfillment
                    pending = system_state.get_pending_commitments(classroom, day, time_slot)
                    for creditor, minutes in pending:
                        prof_agrees = simulate_professor_decision(classroom, "fulfill_commitment")
                        if prof_agrees and random.random() < 0.75:  # 75% fulfillment if professor agrees
                            system_state.fulfill_commitment(classroom, creditor, day, time_slot)
                            print(f"{classroom} fulfilled {minutes}-minute commitment to {creditor}")
                        else:
                            violation_occurred = system_state.record_violation(classroom)
                            print(f"{classroom} failed to fulfill commitment to {creditor}")
                            if violation_occurred:
                                print(f"Violation Event: {classroom} exceeded 3 violations!")
                    
                    # Create new commitments based on negotiation complexity
                    if len(active_classrooms) > 1 and random.random() < 0.5:
                        other_classroom = random.choice([c for c in active_classrooms if c != classroom])
                        minutes = random.choice([2, 4])
                        system_state.add_commitment(classroom, other_classroom, day, time_slot, minutes)
                        print(f"New commitment: {classroom} owes {other_classroom} {minutes} minutes")
                
                # Summary stats
                active_commitments = len([c for c in system_state.commitments.values() if not c['fulfilled']])
                print(f"\nSession Summary:")
                print(f"  1. Active commitments: {active_commitments}")
                print(f"  2. Total violations: {sum(system_state.violations.values())}")
                print(f"  3. Bottleneck efficiency: {'Good' if total_students <= BOTTLENECK_CAPACITY else 'Requires coordination'}")
                
                time.sleep(1)  # Brief pause between simulations

if __name__ == "__main__":
    run_simulation()
    
    print("\n" + "="*70)
    print("Final Report")
    print("="*70)
    
    print(f"\nCommitments:")
    fulfilled = sum(1 for c in system_state.commitments.values() if c["fulfilled"])
    total_commitments = len(system_state.commitments)
    if total_commitments > 0:
        fulfillment_rate = fulfilled/total_commitments*100
        print(f"Total commitments made: {total_commitments}")
        print(f"Commitments fulfilled: {fulfilled}")
        print(f"Fulfillment rate: {fulfillment_rate:.1f}%")
    else:
        print("No commitments were made during simulation")
    
    print(f"\nViolations:")
    violations_found = False
    for agent, violations in system_state.violations.items():
        if violations > 0:
            violations_found = True
            print(f"{agent}: {violations} violations {'(CRITICAL - >3)' if violations > 3 else ''}")
    if not violations_found:
        print("No violations recorded")
    
    print(f"\nRoad Bottleneck:")
    print(f"Final bottleneck capacity: {system_state.current_bottleneck_flow}/min")
    print(f"Last simulation load: {system_state.students_in_transit} students")

    print(f"\nMultiagent Coordination Completed Successfully.")
    