import autogen
from dotenv import load_dotenv
import os

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
CAPACITY = 100  # Max students per batch to avoid congestion
ESTIMATED_TOTAL = 180  # Bottleneck's estimate of total students
ATTENDANCES = {"C1": 50, "C2": 60, "C3": 70}  # Per classroom
SLOTS = [-4, -2, 0, 2, 4]  # Available shift minutes for batches (batches 2 min apart)

# System messages for agents
b_system_message = f"""
You are Agent B, monitoring the bottleneck. Start by broadcasting:
- Current capacity: {CAPACITY} students per 2-minute batch.
- Estimated total students: {ESTIMATED_TOTAL}.
Then, observe and remind agents if congestion is likely to happen. Do not negotiate.
"""

c_system_message_template = """
You are Classroom Agent {name} with {attendance} students attending.
Your goal is to negotiate with other classroom agents to stagger exit times and avoid congestion.
- Propose commitments like: 'If you finish some minutes early (e.g., 2 minutes), I'll finish on time; in return, next time you get extra time.'
- Accept or counter proposals autonomously.
- After a deal, broadcast the revised exit slot and shifted students (e.g., 'C1 shifting to -2 min with 50 students').
- Aim for batches <= {capacity} students.
- Available slots: {slots} minutes from scheduled end.
- Be cooperative but autonomous; refuse if it doesn't suit (e.g., complex topic).
- Track deals in responses.
"""

# Create Agents
b_agent = autogen.AssistantAgent(
    name="B",
    system_message=b_system_message,
    llm_config=llm_config,
)

c1_agent = autogen.AssistantAgent(
    name="C1",
    system_message=c_system_message_template.format(
        name="C1", attendance=ATTENDANCES["C1"], capacity=CAPACITY, slots=SLOTS
    ),
    llm_config=llm_config,
)

c2_agent = autogen.AssistantAgent(
    name="C2",
    system_message=c_system_message_template.format(
        name="C2", attendance=ATTENDANCES["C2"], capacity=CAPACITY, slots=SLOTS
    ),
    llm_config=llm_config,
)

c3_agent = autogen.AssistantAgent(
    name="C3",
    system_message=c_system_message_template.format(
        name="C3", attendance=ATTENDANCES["C3"], capacity=CAPACITY, slots=SLOTS
    ),
    llm_config=llm_config,
)

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
        return b_agent  # Start with B if no valid last_speaker
    current_idx = agents.index(last_speaker)
    next_idx = (current_idx + 1) % len(agents)
    return agents[next_idx]

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
    message="Start the simulation for Monday 11 AM slot. Coordinate to avoid congestion."
)

print("Simulation complete. Check console output for negotiated exits.")