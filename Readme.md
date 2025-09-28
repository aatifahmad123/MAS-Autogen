### Multi Agent System for Classroom Scheduling with Congestion Management

This project implements a multi-agent system (MAS) to optimize classroom scheduling while managing congestion. It uses large language models (LLMs) as agents to collaboratively manage movement of students in and out of classrooms, avoiding congestion on the shared resource: the road leading to the lecture hall complex.

#### Key Features:
- **Multi-Agent Collaboration**: Multiple LLM agents work together to propose and refine classroom schedules
- **Congestion Management**: The system considers classroom capacities and student attendance to minimize congestion during class transitions
- **Dynamic Scheduling**: The timetable is adjusted based on feedback from agents to ensure optimal scheduling
- **Environment Simulation**: Simulates a school environment with predefined classroom capacities and student attendance patterns

#### Requirements:
- The requirements for the project are listed in `requirements.txt`.
- Install using:
  ```bash
  pip install -r requirements.txt
  ```

#### Setup:
1. Clone the repository:
   ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2. Create a `.env` file in the root directory and add your API key:
    ```env
    GEMINI_API_KEY=your_api_key_here
    ```

3. Run the main script:
    ```bash
    python system3.py
    ```

#### Configuration:
- Modify the `config_list` in `system3.py` to change LLM models or parameters.
- Adjust `CAPACITY`, `ATTENDANCES`, `SLOTS`, and `TIMETABLE` variables to simulate different classroom environments and scheduling challenges.

#### Files:
- `system3.py`: Main script implementing the multi-agent system for scheduling
- `README.md`: Project documentation
- `.env`: Environment file for storing API keys (not included in the repository for security reasons)
- `requirements.txt`: List of required Python packages

#### Contributing:
Contributions are welcome! Please fork the repository and submit a pull request with your changes.

