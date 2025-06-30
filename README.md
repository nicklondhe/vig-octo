# Vig-Octo Task Management System

A comprehensive MCP (Model Context Protocol) server for task management with productivity tracking, goal management, and work session analytics.

## Features

### Core Task Management
- **Task CRUD Operations**: Create, read, update, and delete tasks
- **Task Properties**: Name, complexity, type, due date, priority, repeatable status
- **Task Status Tracking**: Pending, in-progress, and completed tasks
- **Task Matrix View**: Organize tasks by priority and complexity in a 3x3 grid

### Goal Management
- **Weekly Goals**: Create and track weekly goals with progress monitoring
- **Goal-Task Relationships**: Link tasks to goals with percentage splits
- **Progress Tracking**: Automatic goal progress updates based on task completion
- **Progress History**: Detailed history of goal progress over time

### Work Session Management
- **Session Tracking**: Start and end work sessions with context and queries
- **Work Logs**: Track time spent on specific tasks within sessions
- **Effectiveness Ratings**: Rate session effectiveness (1-5 scale)
- **Session Analytics**: Detailed session information with recommendations

### Productivity Analytics
- **Velocity Stats**: Track productivity metrics over customizable time frames
- **Time Tracking**: Monitor time spent on tasks and sessions
- **Completion Rates**: Track task completion percentages
- **Weekday Productivity**: Analyze productivity patterns by day of week

### Task Recommendations
- **Smart Recommendations**: AI-powered task recommendations for work sessions
- **Recommendation Status**: Accept or reject recommendations with reasons
- **Strategy-Based**: Support for different recommendation strategies

## Installation

### Prerequisites
- Python 3.10 or higher
- SQLite (included with Python)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd vig-octo
   ```

2. **Create and activate virtual environment**:
   ```bash
   uv venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   uv pip install -r requirements.txt
   ```

4. **Install development dependencies** (optional):
   ```bash
   uv pip install -r requirements-dev.txt
   ```

## Usage

### Starting the Server

```bash
source .venv/bin/activate
python server.py
```

### Development Commands

- **Run tests**: `pytest`
- **Lint code**: `flake8 *.py`
- **Type check**: `mypy --strict *.py`
- **Format code**: `black *.py`
- **Single test**: `pytest test_file.py::test_function -v`

## API Endpoints

### Task Management
- `add_task(task_data: AddTaskRequest)` - Create a new task
- `update_task(task_id: int, task_data: UpdateTaskRequest)` - Update existing task
- `mark_task_status(task_id: int, status: str)` - Change task status
- `list_pending_tasks()` - Get all pending tasks
- `list_completed_repeatable_tasks()` - Get completed repeatable tasks
- `get_task_matrix_view(limit: int, sort_by: str)` - Get task matrix view

### Goal Management
- `create_weekly_goal(goal_data: AddWeeklyGoalRequest)` - Create weekly goal
- `list_weekly_goals(date: datetime)` - List goals for specific week
- `update_goal_progress(progress_data: UpdateGoalProgressRequest)` - Update goal progress
- `get_goal_progress(goal_id: int)` - Get goal progress and history

### Session Management
- `start_session(session_data: StartSessionRequest)` - Start work session
- `end_session(end_data: EndSessionRequest)` - End work session
- `get_sessions(limit: int, days: int)` - List work sessions
- `get_session_details(session_id: int)` - Get detailed session info

### Work Log Management
- `start_work_log(log_data: StartWorkLogRequest)` - Start work log
- `end_work_log(end_data: EndWorkLogRequest)` - End work log

### Analytics
- `get_velocity_stats(stats_data: VelocityStatsRequest)` - Get productivity stats

### Recommendations
- `save_recommendations(recommendation_data: SaveRecommendationsRequest)` - Save recommendations
- `update_recommendation_status(status_data: UpdateRecommendationStatusRequest)` - Update recommendation status

## Data Models

### Task Properties
- **name**: Task name (required)
- **complexity**: simple, medium, complex
- **type**: Direct, Research, Planning, etc.
- **due_date**: Optional due date (can be cleared with null)
- **priority**: low, medium, high
- **repeatable**: Boolean flag for recurring tasks
- **status**: pending, done

### Goal Properties
- **title**: Goal title (required)
- **description**: Optional description
- **category**: Optional category
- **start_date**: Goal start date
- **end_date**: Optional end date
- **status**: pending, in_progress, completed

## Database Schema

The system uses SQLite with the following main tables:
- `tasks` - Core task information
- `weekly_goals` - Goal definitions
- `goal_tasks` - Task-goal relationships
- `goal_progress_history` - Goal progress tracking
- `work_sessions` - Work session records
- `work_logs` - Time tracking for tasks
- `recommendations` - Task recommendations
- `task_summaries` - Task summary statistics

## Configuration

The system uses configuration from `config.py` with environment-specific settings:
- Database path configuration
- Environment type (dev/prod)
- Version information

## Testing

Run the test suite:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=server --cov-report=term-missing
```

## Contributing

1. Follow PEP 8 style guidelines
2. Use type hints for all functions
3. Add docstrings with triple single quotes
4. Write tests for new features
5. Run linting and type checking before committing

## Code Style Guidelines

- Use docstrings with triple single quotes `'''` for all modules, classes, and functions
- Follow PEP style guidelines
- Imports: standard lib first, then third-party, then local
- Use type hints for all function parameters and return values
- Variables: snake_case for variables, CamelCase for classes
- SQLAlchemy models: suffix with "Model" (e.g., TaskModel)
- Pydantic models: no suffix (e.g., Task)
- Error handling: use try/except with specific exceptions

## License

[License information to be added]

## Version

Current version: 0.1.0