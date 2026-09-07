# 🚀 WorkPilot AI

> **An AI employee that understands your work, plans your day, and executes tasks for you.**

WorkPilot AI is an **autonomous AI work-management platform** that combines personal work context, enterprise knowledge, intelligent planning, workplace automation, persistent memory, and human-in-the-loop approval.

Unlike a traditional chatbot that only answers questions, WorkPilot is designed to **understand work, plan actions, safely execute tasks, and verify the results**.

---

## 🏆 Hackathon Project

WorkPilot AI demonstrates how **Agentic AI** can be applied to real-world workplace productivity.

The system combines:

* 🤖 Multi-Agent AI
* 🧠 Persistent Memory
* 📚 Retrieval-Augmented Generation (RAG)
* 📧 Email Automation
* 📅 Calendar Management
* 💬 Slack Integration
* 🎫 Jira Integration
* ✅ Task Management
* 📝 Notes
* 🔐 Role-Aware Knowledge Access
* 🧑‍⚖️ Human-in-the-Loop Approval
* ⚡ n8n Workflow Automation
* 🔎 Execution Verification

---

# 💡 The Problem

Modern professionals work across multiple tools every day:

* Email
* Calendar
* Slack
* Jira
* Company documents
* Task lists
* Notes

Traditional productivity tools require users to manually switch between these systems.

Generic AI assistants can answer questions, but they often lack:

* Awareness of the user's current work
* Access to organizational knowledge
* Persistent memory
* Multi-step planning
* Real workplace integrations
* Controlled action execution
* Verification of completed actions

This creates a gap between **AI that can talk** and **AI that can actually help get work done**.

---

# 💎 Our Solution

WorkPilot AI acts as an **AI work employee** that connects knowledge, planning, memory, and workplace automation into one system.

Instead of:

```text
User → Ask Question → AI → Answer
```

WorkPilot follows:

```text
User Request
     ↓
Understand
     ↓
Plan
     ↓
Select Specialist
     ↓
Review / Approve
     ↓
Execute
     ↓
Verify
     ↓
Remember
```

This transforms the AI from a simple conversational interface into a **context-aware agentic work-management system**.

---

# ✨ Key Features

## 🤖 Autonomous Work Management

Users can interact with WorkPilot using natural language.

Examples:

> "Plan my day based on my pending tasks."

> "Find the company's leave policy."

> "Draft an email to the team."

> "Schedule a meeting for tomorrow."

> "Send this update to Slack."

> "Show me my recent emails."

The system determines what type of request it is and routes it to the appropriate AI capability.

---

## 🧠 Work-Aware AI

WorkPilot maintains awareness of the user's work context.

The AI can use information such as:

* Tasks
* Notes
* Calendar information
* Conversation history
* Recent work activity
* Enterprise documents

This enables more personalized and context-aware responses.

Instead of asking:

> "What tasks do I have?"

the user can ask:

> "What should I focus on today?"

and WorkPilot can reason over the available work context.

---

# 📋 Task Management

WorkPilot provides task management capabilities for organizing daily work.

Users can:

* Create tasks
* View tasks
* Update task status
* Set priorities
* Track deadlines
* Review pending work

The AI can also use task information when generating daily plans.

### Example

```text
User:
"Plan my day."

        ↓

WorkPilot reviews:
• Pending tasks
• Priorities
• Deadlines
• Calendar

        ↓

AI-generated daily plan
```

---

# 📝 Notes

Users can create and manage work notes through the WorkPilot workspace.

Notes can also become part of the user's work context, allowing the AI to provide more relevant assistance.

---

# 📅 Calendar Management

WorkPilot integrates calendar operations into the AI workflow.

Capabilities include:

* Reading calendar information
* Understanding scheduled events
* Preparing calendar actions
* Creating calendar events
* Using calendar context for daily planning

Example:

```text
User:
"Schedule a team meeting tomorrow at 3 PM."

        ↓
AI prepares the event
        ↓
Human approval
        ↓
Calendar execution
        ↓
Execution verification
```

---

# 📧 Email Automation

WorkPilot can assist with workplace email workflows.

Capabilities include:

* Reading recent emails
* Drafting emails
* Sending emails
* Preparing broadcast emails
* Sending replies
* Analyzing complaint-related emails

Example:

```text
User
 ↓
"Send an email to the team about tomorrow's meeting."
 ↓
Email Agent
 ↓
Generate proposed email
 ↓
Human Approval
 ↓
Send
 ↓
Verify
```

---

# 💬 Slack Integration

WorkPilot can interact with Slack-based workplace workflows.

Capabilities include:

* Preparing Slack messages
* Sending notifications
* Sending workplace updates
* Sending complaint notifications

This allows WorkPilot to move from generating information to performing controlled workplace communication.

---

# 🎫 Jira Integration

WorkPilot can interact with Jira workflows.

Capabilities include:

* Retrieving Jira issues
* Preparing Jira updates
* Supporting Jira issue creation/update workflows

Jira-related operations are incorporated into the agentic workflow rather than allowing uncontrolled external execution.

---

# 📚 Enterprise Knowledge with RAG

WorkPilot includes a **Retrieval-Augmented Generation (RAG)** system for answering questions from company documents.

### RAG Pipeline

```text
Company Documents
       ↓
Document Processing
       ↓
Text Chunking
       ↓
Embeddings
       ↓
ChromaDB
       ↓
Semantic Retrieval
       ↓
Relevant Context
       ↓
LLM
       ↓
Grounded Answer
```

### Technologies

* ChromaDB
* Sentence Transformers
* `BAAI/bge-small-en-v1.5`
* Mistral
* LangChain

Users can ask:

```text
"What is the company's leave policy?"

"Summarize the HR guidelines."

"What does the employee handbook say about remote work?"
```

The system retrieves relevant organizational information before generating the response.

---

# 🔐 Role-Aware Knowledge Access

Enterprise information can be accessed according to user roles and permissions.

This allows WorkPilot to support different levels of access to organizational knowledge.

For example:

```text
Manager
   │
   ├── General Company Documents
   ├── HR Information
   └── Management Resources


Employee
   │
   ├── General Company Documents
   └── Employee Resources
```

This makes the RAG system more suitable for enterprise environments where information access needs to be controlled.

---

# 🧩 Multi-Agent Architecture

WorkPilot uses a **Supervisor–Planner–Worker architecture** built with LangGraph.

Instead of relying on a single AI agent for everything, WorkPilot routes requests to specialized agents.

### Main Components

* **Supervisor Agent** — understands intent and routes requests
* **Planner Agent** — determines the required workflow
* **RAG Agent** — retrieves enterprise knowledge
* **Email Agent** — handles email workflows
* **Calendar Agent** — handles calendar operations
* **Slack Agent** — handles Slack communication
* **Jira Agent** — handles Jira workflows
* **Research Agent** — handles research-oriented requests
* **Memory Layer** — stores persistent context
* **Responder** — generates the final user response

---

# 🏗️ System Architecture

```text
                         ┌──────────────┐
                         │     User     │
                         └──────┬───────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Streamlit UI  │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │    FastAPI      │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │    Supervisor   │
                       └────────┬────────┘
                                │
                                ▼
                         ┌─────────────┐
                         │   Planner   │
                         └──────┬──────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │          │          │          │          │
          ▼          ▼          ▼          ▼          ▼
        RAG       Email      Calendar    Slack      Jira
       Agent      Agent       Agent      Agent      Agent
          │          │          │          │          │
          └──────────┴──────────┼──────────┴──────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Human Approval  │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  n8n Workflows  │
                       └────────┬────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
                  Gmail      Calendar     Slack/Jira
                                │
                                ▼
                       Execution Results
                                │
                                ▼
                       ┌─────────────────┐
                       │ Persistent      │
                       │ Memory          │
                       └─────────────────┘
```

---

# 🔄 Agentic Workflow

A typical action request follows:

```text
1. User Request
       ↓
2. Load Memory
       ↓
3. Supervisor Classification
       ↓
4. Planning
       ↓
5. Specialist Agent
       ↓
6. Human Review
       ↓
7. Tool Execution
       ↓
8. Execution Verification
       ↓
9. Save Results
       ↓
10. Final Response
```

Read-only requests can bypass human approval when no external side effect is involved.

---

# 🧑‍⚖️ Human-in-the-Loop Safety

One of WorkPilot's key design principles is:

> **AI should not perform consequential actions blindly.**

For actions that can create external side effects, WorkPilot can pause for human approval.

```text
AI Decision
     ↓
Action Proposal
     ↓
Human Review
     │
 ┌───┴────┐
 ▼        ▼
Approve  Reject
 │        │
 ▼        ▼
Execute   Stop
```

If an action is rejected:

```text
Action rejected — nothing was executed.
```

This provides an important safety layer for workplace automation.

---

# 🛡️ Safe Tool Execution

WorkPilot separates **information retrieval** from **external actions**.

For example, a calendar request intended to retrieve information should not accidentally create or modify an event.

The system therefore applies controlled processing before requests reach external automation workflows.

### Design Principle

```text
Read Information
       ↓
Reason About Action
       ↓
Request Approval
       ↓
Execute
```

This reduces the risk of unintended tool execution.

---

# ⚡ n8n Automation Layer

WorkPilot uses **n8n** as the workflow automation and integration layer.

Instead of tightly coupling every external service directly to the AI agents, WorkPilot sends structured action requests to n8n.

```text
LangGraph
    │
    ▼
Structured Action
    │
    ▼
n8n Webhook
    │
    ▼
n8n Workflow
    │
    ├── Email
    ├── Calendar
    ├── Slack
    └── Jira
```

This architecture makes workplace integrations easier to maintain and extend.

---

# 💾 Persistent Memory

WorkPilot uses multiple memory mechanisms.

### PostgreSQL

Used for structured application memory and persistent state.

Example database:

```text
agent_memory
```

Data can include:

* Memory
* Agent state
* Action logs
* Work context

### LangGraph MemorySaver

Used for graph checkpoints and conversational state.

### ChromaDB

Used for semantic enterprise knowledge retrieval.

### Combined Architecture

```text
                  WorkPilot Memory
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     PostgreSQL      LangGraph      ChromaDB
     Structured      Checkpoints    Semantic
       Memory          / State      Knowledge
```

---

# 🔎 Execution Verification

WorkPilot does not simply assume that an action succeeded.

After execution, the system records structured results.

Example:

```text
Action:
send_email

Status:
Success

Details:
Email sent successfully
```

If execution fails:

```text
Action:
create_calendar_event

Status:
Failed

Details:
Calendar service returned an error
```

The final response is generated using the actual execution results.

This creates a reliable:

> **Plan → Execute → Verify**

workflow.

---

# 📊 Intelligent Dashboard

The WorkPilot dashboard provides a centralized view of the user's work.

It can display:

* Today's tasks
* Upcoming tasks
* Recent notes
* Calendar information
* Work statistics
* AI-generated daily planning
* Recent activity

The dashboard serves as the user's **AI-powered work command center**.

---

# 📁 Project Structure

```text
WorkPilot-AI/
│
├── agents/
│   ├── planner.py
│   ├── executor.py
│   ├── rag_agent.py
│   └── email_agent.py
│
├── graph.py
├── state.py
├── supervisor.py
├── config.py
│
├── memory/
│   └── ...
│
├── workflows/
│   └── ...
│
├── frontend/
│   └── ...
│
├── backend/
│   └── ...
│
├── chroma_db/
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

---

# 🛠️ Technology Stack

| Category            | Technology            |
| ------------------- | --------------------- |
| Language            | Python                |
| Agent Framework     | LangGraph             |
| LLM Framework       | LangChain             |
| LLM                 | Groq / Mistral        |
| Embeddings          | Sentence Transformers |
| Vector Database     | ChromaDB              |
| Database            | PostgreSQL            |
| Automation          | n8n                   |
| Backend             | FastAPI               |
| Frontend            | Streamlit             |
| Containerization    | Docker                |
| Document Processing | PyPDF                 |
| Environment         | python-dotenv         |

---

# 🚀 Getting Started

## 1. Clone the Repository

```bash
git clone <your-repository-url>
cd WorkPilot-AI
```

## 2. Create a Virtual Environment

```bash
python -m venv fastenv
```

Activate it on Windows:

```bash
fastenv\Scripts\activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Environment Variables

Create a `.env` file containing the required credentials and service configuration.

The project requires configuration for:

* Groq API
* Mistral API
* PostgreSQL
* n8n

> **Do not commit API keys, passwords, or `.env` files to GitHub.**

## 5. Start the Backend

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

FastAPI:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## 6. Start the Frontend

```bash
streamlit run app.py
```

Make sure PostgreSQL and the required n8n workflows are running before using integrations.

---

# 💻 Example Use Cases

### 1. Daily Planning

```text
User:
"Plan my workday."

WorkPilot:
→ Loads work context
→ Reviews tasks and calendar
→ Prioritizes work
→ Generates a daily plan
```

### 2. Enterprise Knowledge

```text
User:
"What is the company's leave policy?"

WorkPilot:
→ Searches company documents
→ Retrieves relevant information
→ Generates grounded answer
```

### 3. Email Automation

```text
User:
"Send an update to the team."

WorkPilot:
→ Understands request
→ Drafts message
→ Requests approval
→ Sends email
→ Verifies execution
```

### 4. Calendar Automation

```text
User:
"Schedule a meeting tomorrow at 3 PM."

WorkPilot:
→ Prepares calendar event
→ Requests approval
→ Creates event
→ Confirms result
```

### 5. Workplace Complaint

```text
Complaint Email
      ↓
AI Analysis
      ↓
Prepare Response
      ↓
Slack Notification
      ↓
Follow-up Action
      ↓
Human Approval
      ↓
Execute
      ↓
Verify
```

---

# 🔐 Security & Design Principles

WorkPilot follows several principles for safer enterprise AI:

### Human Approval

Consequential external actions can require explicit user approval.

### Controlled Tool Access

AI agents interact with external services through defined workflows.

### Read/Write Separation

Read-only operations are handled differently from actions that modify external systems.

### No Hardcoded Secrets

Credentials are stored through environment variables.

### Execution Verification

The system records whether an action succeeded or failed.

### Persistent State

Important workflow information can be stored for future interactions.

### Role-Aware Knowledge

Enterprise information can be restricted according to user permissions.

---

# 🌟 What Makes the Project Innovative?

WorkPilot brings multiple AI capabilities together into a single agentic workflow:

```text
              ┌────────────────────┐
              │   Enterprise RAG   │
              └─────────┬──────────┘
                        │
┌──────────────┐        ▼        ┌───────────────┐
│ Work Context │ ──► AI Planner ◄──│  AI Memory   │
└──────────────┘        │        └───────────────┘
                        │
                        ▼
                Specialist Agents
                        │
                        ▼
                 Human Approval
                        │
                        ▼
                Workplace Tools
                        │
                        ▼
                Result Verification
```

The key innovation is not simply using an LLM.

It is combining:

**Context + Reasoning + Planning + Memory + Tools + Safety + Verification**

into one workflow.

---

# 🎯 Project Goals

WorkPilot AI was built to demonstrate how modern Agentic AI can move beyond simple question-answering toward **context-aware workplace automation**.

The project demonstrates practical implementation of:

* Large Language Models
* Retrieval-Augmented Generation
* Multi-Agent Systems
* LangGraph orchestration
* Tool calling
* Workflow automation
* Persistent memory
* Human-in-the-loop systems
* Enterprise knowledge retrieval
* API-based architecture
* External workplace integrations

The core idea is:

> **Understand work → Plan work → Execute work → Verify work → Remember work**

---

# 🔮 Future Improvements

Planned enhancements include:

* More workplace integrations
* Advanced autonomous task planning
* Improved long-term memory
* Calendar optimization
* Intelligent email prioritization
* AI-generated daily briefings
* Advanced work analytics
* More granular RBAC
* Improved tool-failure recovery
* Agent evaluation and observability
* Automated workflow testing
* Production-grade authentication
* Enterprise SSO
* Scalable cloud deployment

---

# 🎥 Demo

Add your hackathon demo video here:

```text
[Watch WorkPilot AI Demo](YOUR-DEMO-LINK)
```

---

# 🖼️ Screenshots



1. WorkPilot Dashboard
![Approval](assets/welcome.png)
![Approval](assets/manager_panel.png) 

2. Daily Planning
![Approval](assets/plan_day.png)
3. RAG / Document Q&A
![Approval](assets/Rag.png) 
5. Human Approval Interface
![Approval](assets/event_approval.png) 
6. Task Management
7. Calendar / Email Automation
![Approval](assets/event_creation.png)

---

# 📌 Project Status

**WorkPilot AI is a hackathon-ready prototype demonstrating an autonomous, context-aware AI work-management system.**

The project focuses on combining **Agentic AI, RAG, persistent memory, workplace automation, and human oversight** into a practical AI employee experience.

---

# 🧠 Built With

**Python · LangGraph · LangChain · Groq · Mistral · ChromaDB · Sentence Transformers · PostgreSQL · n8n · FastAPI · Streamlit · Docker**

---

## 👩‍💻 Hackathon Vision

> **WorkPilot isn't just an AI that answers your questions.
> It's an AI that understands your work, plans what needs to happen, and helps you get it done — safely.**


