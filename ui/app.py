"""AI Ops Assistant - Production-Ready Streamlit UI."""

import json
import time
import streamlit as st
import httpx
from datetime import datetime

API_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="AI Ops Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { padding: 10px 20px; }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .step-success { border-left: 4px solid #28a745; padding-left: 10px; }
    .step-failed { border-left: 4px solid #dc3545; padding-left: 10px; }
    .step-pending { border-left: 4px solid #ffc107; padding-left: 10px; }
    .timeline-event { 
        padding: 10px; 
        margin: 5px 0; 
        border-radius: 5px; 
        background: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "task_history" not in st.session_state:
    st.session_state.task_history = []
if "current_task_id" not in st.session_state:
    st.session_state.current_task_id = None
if "execution_logs" not in st.session_state:
    st.session_state.execution_logs = []

# Header
st.title("🤖 AI Operations Assistant")
st.caption("Intelligent automation for AIOps, DevOps & MLOps tasks")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    user_id = st.text_input("User ID", value="demo_user", help="Unique identifier for task isolation")
    
    st.markdown("---")
    
    st.header("🎯 Quick Actions")
    example_tasks = {
        "📦 Get Repo Info": "Get information about facebook/react repository",
        "🔍 Search Repos": "Search for repositories about machine learning",
        "📋 List Issues": "List open issues in vercel/next.js",
        "📄 Get README": "Get the README file from langchain-ai/langchain",
    }
    
    for label, task in example_tasks.items():
        if st.button(label, use_container_width=True):
            st.session_state.quick_task = task
    
    st.markdown("---")
    
    # Task history in sidebar
    st.header("📜 Recent Tasks")
    if st.button("🔄 Load History", use_container_width=True):
        try:
            r = httpx.get(f"{API_URL}/tasks/history/{user_id}", timeout=10)
            if r.status_code == 200:
                st.session_state.task_history = r.json().get("tasks", [])
        except:
            st.error("Could not load history")
    
    for task in st.session_state.task_history[:5]:
        status_icon = "✅" if task.get("status") == "completed" else "❌"
        with st.expander(f"{status_icon} {task.get('prompt', '')[:30]}..."):
            st.write(f"**Task ID:** {task.get('task_id')}")
            st.write(f"**Status:** {task.get('status')}")
            st.write(f"**Confidence:** {task.get('confidence', 0):.0%}")
            if st.button("View Logs", key=task.get('task_id')):
                st.session_state.current_task_id = task.get('task_id')

# Main content tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Execute Task", "📊 Execution Logs", "📈 Analytics", "🔧 System Info"])

# TAB 1: Execute Task
with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 Task Input")
        
        # Use quick task if set
        default_prompt = st.session_state.get("quick_task", "")
        if default_prompt:
            del st.session_state.quick_task
        
        prompt = st.text_area(
            "Describe your task:",
            value=default_prompt,
            height=120,
            placeholder="e.g., Get the star count and description of facebook/react repository"
        )
        
        with st.expander("🔧 Advanced Options"):
            context = st.text_area("Additional Context (JSON)", value="{}", height=80)
            priority = st.select_slider("Priority", options=["low", "default", "high"], value="default")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            stream_btn = st.button("⚡ Stream Execute", type="primary", use_container_width=True)
        with col_btn2:
            queue_btn = st.button("📤 Queue Task", use_container_width=True)
    
    with col2:
        st.subheader("📋 Execution Progress")
        progress_container = st.container()
        
        # Progress display area
        with progress_container:
            if "current_status" in st.session_state:
                st.info(st.session_state.current_status)
    
    st.markdown("---")
    
    # Results section
    res_col1, res_col2 = st.columns([1, 1])
    
    with res_col1:
        st.subheader("🧠 LLM Reasoning")
        thinking_placeholder = st.empty()
    
    with res_col2:
        st.subheader("📊 Plan & Results")
        results_placeholder = st.empty()
    
    # Stream execution
    if stream_btn and prompt:
        thinking_text = ""
        plan_data = None
        
        with progress_container:
            progress_bar = st.progress(0, text="Initializing...")
        
        try:
            with httpx.Client(timeout=120) as client:
                with client.stream(
                    "POST",
                    f"{API_URL}/tasks/stream",
                    json={"user_id": user_id, "prompt": prompt},
                ) as response:
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            try:
                                event = json.loads(data.replace("'", '"'))
                                event_type = event.get("event")
                                
                                if event_type == "start":
                                    st.session_state.current_task_id = event.get("task_id")
                                    progress_bar.progress(10, text=f"✅ Task started: {event.get('task_id')}")
                                
                                elif event_type == "planning":
                                    progress_bar.progress(20, text="🧠 LLM is planning...")
                                
                                elif event_type == "chunk":
                                    thinking_text += event.get("content", "").replace("\\n", "\n")
                                    thinking_placeholder.code(thinking_text, language="json")
                                    progress_bar.progress(40, text="🧠 Generating plan...")
                                
                                elif event_type == "plan_complete":
                                    progress_bar.progress(60, text="✅ Plan generated!")
                                    plan = event.get("plan", {})
                                    if isinstance(plan, str):
                                        plan = json.loads(plan)
                                    plan_data = plan
                                    
                                    with results_placeholder:
                                        st.markdown("**📋 Execution Plan:**")
                                        
                                        # Show thinking
                                        if plan.get("thinking"):
                                            st.info(f"💭 {plan.get('thinking')}")
                                        
                                        # Show steps
                                        steps = plan.get("steps", [])
                                        for i, step in enumerate(steps):
                                            deps = step.get("depends_on", [])
                                            dep_str = f" (depends: {deps})" if deps else ""
                                            st.markdown(f"""
                                            **Step {i+1}: {step.get('step_id')}**
                                            - Tool: `{step.get('tool')}`
                                            - Params: `{step.get('params')}`{dep_str}
                                            """)
                                
                                elif event_type == "done":
                                    progress_bar.progress(100, text="✅ Complete!")
                                    trace_url = event.get("trace_url")
                                    if trace_url:
                                        st.session_state.trace_url = trace_url
                                        st.success(f"🔗 [View Full Trace in Langfuse]({trace_url})")
                                        
                            except json.JSONDecodeError:
                                pass
                                
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    # Queue execution
    if queue_btn and prompt:
        with progress_container:
            st.info("⏳ Submitting to processing queue...")
        
        try:
            r = httpx.post(
                f"{API_URL}/tasks/",
                json={"user_id": user_id, "prompt": prompt, "priority": priority},
                timeout=30
            )
            
            if r.status_code == 200:
                data = r.json()
                task_id = data["task_id"]
                st.session_state.current_task_id = task_id
                
                with progress_container:
                    st.success(f"✅ Task queued: {task_id}")
                    
                    # Poll for result
                    poll_progress = st.progress(0, text="Waiting for result...")
                    
                    for i in range(60):
                        time.sleep(1)
                        poll_progress.progress(min(i * 2, 95), text=f"Polling... ({i}s)")
                        
                        result = httpx.get(
                            f"{API_URL}/tasks/{task_id}",
                            params={"user_id": user_id},
                            timeout=10
                        )
                        
                        if result.status_code == 200:
                            res = result.json()
                            
                            if res["status"] in ["completed", "failed"]:
                                poll_progress.progress(100, text=f"Status: {res['status']}")
                                
                                with results_placeholder:
                                    if res["status"] == "completed":
                                        st.success(f"✅ Completed with {res.get('confidence', 0):.0%} confidence")
                                        if res.get("result"):
                                            st.json(res["result"])
                                    else:
                                        st.error("❌ Task failed")
                                        for err in res.get("errors", []):
                                            st.error(err)
                                break
            else:
                st.error(f"Error: {r.text}")
                
        except Exception as e:
            st.error(f"❌ Error: {e}")

# TAB 2: Execution Logs
with tab2:
    st.subheader("🔍 Detailed Execution Logs")
    
    log_col1, log_col2 = st.columns([1, 3])
    
    with log_col1:
        task_id_input = st.text_input(
            "Task ID",
            value=st.session_state.get("current_task_id", ""),
            help="Enter task ID to view execution logs"
        )
        
        if st.button("📥 Load Logs", use_container_width=True):
            if task_id_input:
                try:
                    r = httpx.get(
                        f"{API_URL}/tasks/logs/{task_id_input}",
                        params={"user_id": user_id},
                        timeout=30
                    )
                    if r.status_code == 200:
                        st.session_state.execution_logs = r.json()
                        st.success("Logs loaded!")
                    else:
                        st.error("No logs found")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    with log_col2:
        logs_data = st.session_state.get("execution_logs", {})
        
        if logs_data:
            # Summary metrics
            st.markdown("### 📊 Execution Summary")
            
            metric_cols = st.columns(4)
            with metric_cols[0]:
                st.metric("Total Events", logs_data.get("total_events", 0))
            with metric_cols[1]:
                event_types = logs_data.get("event_types", {})
                st.metric("Steps Executed", event_types.get("step_complete", 0))
            with metric_cols[2]:
                st.metric("Verifications", event_types.get("verify", 0))
            with metric_cols[3]:
                st.metric("Replans", event_types.get("replan", 0))
            
            st.markdown("---")
            
            # Timeline
            st.markdown("### 📜 Event Timeline")
            
            timeline = logs_data.get("timeline", [])
            
            for event in timeline:
                event_type = event.get("event_type", "")
                event_name = event.get("event_name", "")
                decision = event.get("decision", "")
                success = event.get("success", True)
                latency = event.get("latency_ms", 0)
                
                # Color based on event type
                colors = {
                    "guardrails": "🛡️",
                    "planning": "🧠",
                    "step_start": "▶️",
                    "step_complete": "✅" if success else "❌",
                    "verify": "🔍",
                    "replan": "🔄",
                    "completion": "🏁",
                }
                
                icon = colors.get(event_type, "📌")
                
                with st.expander(f"{icon} **{event_name}** | {decision} | {latency}ms"):
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.markdown("**Input:**")
                        st.json(event.get("input_data", {}))
                    
                    with col_b:
                        st.markdown("**Output:**")
                        st.json(event.get("output_data", {}))
                    
                    if event.get("decision_reason"):
                        st.info(f"💭 Reason: {event.get('decision_reason')}")
                    
                    if event.get("llm_thinking"):
                        st.markdown("**LLM Thinking:**")
                        st.code(event.get("llm_thinking"))
                    
                    if event.get("error_message"):
                        st.error(f"Error: {event.get('error_message')}")
        else:
            st.info("👆 Enter a Task ID and click 'Load Logs' to view execution details")

# TAB 3: Analytics
with tab3:
    st.subheader("📈 Task Analytics")
    
    if st.button("🔄 Refresh Stats", use_container_width=False):
        try:
            r = httpx.get(f"{API_URL}/tasks/stats/{user_id}", timeout=10)
            if r.status_code == 200:
                st.session_state.stats = r.json()
        except:
            st.error("Could not load stats")
    
    stats = st.session_state.get("stats", {})
    
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Tasks", stats.get("total", 0))
        with col2:
            st.metric("Completed", stats.get("completed", 0))
        with col3:
            st.metric("Failed", stats.get("failed", 0))
        with col4:
            total = stats.get("total", 1)
            completed = stats.get("completed", 0)
            rate = (completed / total * 100) if total > 0 else 0
            st.metric("Success Rate", f"{rate:.1f}%")
        
        st.markdown("---")
        
        # Task status breakdown
        st.markdown("### Status Breakdown")
        status_data = {
            "Completed": stats.get("completed", 0),
            "Failed": stats.get("failed", 0),
            "Pending": stats.get("pending", 0),
        }
        st.bar_chart(status_data)
    else:
        st.info("Click 'Refresh Stats' to load analytics")

# TAB 4: System Info
with tab4:
    st.subheader("🔧 System Architecture")
    
    st.markdown("""
    ### Agent Pipeline Flow
    
    ```
    User Input → Guardrails → Planner → Executor → Verifier → Output
                    │            │          │           │
                    │            │          │           │
                    └────────────┴──────────┴───────────┘
                                      │
                                 Execution Logs
                                 (PostgreSQL)
    ```
    
    ### Components
    
    | Component | Technology | Purpose |
    |-----------|------------|---------|
    | **API** | FastAPI | REST endpoints, streaming |
    | **UI** | Streamlit | Interactive dashboard |
    | **Queue** | Redis RQ | Async task processing |
    | **Database** | PostgreSQL | Persistent storage |
    | **Observability** | Langfuse | LLM tracing |
    | **Guardrails** | NeMo Guardrails | Input validation |
    
    ### Features
    
    - ✅ Chain-of-Thought planning with few-shot examples
    - ✅ Step-by-step verification after each execution
    - ✅ Automatic replanning on failure
    - ✅ Granular execution logging
    - ✅ Multi-user task isolation
    - ✅ Real-time streaming responses
    - ✅ Production-grade error handling with retries
    """)
    
    st.markdown("---")
    
    st.markdown("### API Health Check")
    if st.button("🏥 Check API"):
        try:
            r = httpx.get(f"{API_URL}/health", timeout=5)
            if r.status_code == 200:
                st.success("✅ API is healthy")
            else:
                st.warning(f"⚠️ API returned {r.status_code}")
        except:
            st.error("❌ API is not reachable")

# Footer
st.markdown("---")
st.caption("AI Operations Assistant | Built with LangGraph, FastAPI, Streamlit")
