import streamlit as st
import pandas as pd
import tempfile
import os
from pathlib import Path
import sys

# Add parent directory to path to import local modules
sys.path.append(str(Path(__file__).parent))

from vector import get_retriever, load_client_data, create_documents
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

# Set page config
st.set_page_config(
    page_title="Spreadsheet Q&A Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional appearance
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1a1f2e;
        border-right: 1px solid #2d3548;
    }
    
    /* Chat message styling */
    .stChatMessage {
        background-color: #1a1f2e;
        border: 1px solid #2d3548;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    
    /* Button styling */
    .stButton > button {
        background-color: #4a5568;
        border: none;
        border-radius: 8px;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #5a6578;
        transform: translateY(-2px);
    }
    
    /* Primary button */
    .stButton > button[kind="primary"] {
        background-color: #3182ce;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #4192de;
    }
    
    /* Radio button styling */
    .stRadio > div {
        background-color: #1a1f2e;
        padding: 10px;
        border-radius: 8px;
    }
    
    /* Success/Error message styling */
    .stSuccess, .stError, .stWarning, .stInfo {
        border-radius: 8px;
        padding: 10px;
    }
    
    /* Header styling */
    h1, h2, h3 {
        color: #e2e8f0;
    }
    
    /* Mode selector card */
    .mode-card {
        background-color: #1a1f2e;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2d3548;
        margin-bottom: 20px;
        text-align: center;
    }
    
    /* Feature cards */
    .feature-card {
        background-color: #1a1f2e;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2d3548;
        height: 100%;
        transition: transform 0.3s;
    }
    
    .feature-card:hover {
        transform: translateY(-5px);
        border-color: #3182ce;
    }
    
    /* Chat input styling */
    .stChatInputContainer {
        border-top: 1px solid #2d3548;
        padding-top: 20px;
    }
    
    /* File uploader */
    .stFileUploader {
        background-color: #1a1f2e;
        border: 2px dashed #2d3548;
        border-radius: 10px;
        padding: 20px;
    }
    
    .stFileUploader:hover {
        border-color: #3182ce;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'retriever' not in st.session_state:
    st.session_state.retriever = None
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'current_data_source' not in st.session_state:
    st.session_state.current_data_source = None
if 'deployment_mode' not in st.session_state:
    st.session_state.deployment_mode = "LOCAL"
if 'pending_question' not in st.session_state:
    st.session_state.pending_question = None

# Header with better styling
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <h1 style='color: #3182ce; margin-bottom: 10px;'>📊 Spreadsheet Q&A Assistant</h1>
        <p style='color: #a0aec0; font-size: 18px;'>Ask questions about your data in natural language</p>
    </div>
    """, unsafe_allow_html=True)

# Deployment Mode Selector
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    deployment_mode = st.radio(
        "🌐 Deployment Mode",
        ["LOCAL", "CLOUD"],
        index=0,
        horizontal=True,
        help="Cloud mode coming soon! Currently only local mode is available."
    )
    st.session_state.deployment_mode = deployment_mode

# Show elegant warning if cloud mode is selected
if deployment_mode == "CLOUD":
    st.markdown("""
    <div style='background-color: #1a1f2e; padding: 30px; border-radius: 10px; border: 1px solid #3182ce; margin: 20px 0;'>
        <h3 style='color: #3182ce; margin-bottom: 15px;'>☁️ Cloud Mode - Coming Soon!</h3>
        <p style='color: #a0aec0; margin-bottom: 20px;'>We're working hard to bring you cloud capabilities. Stay tuned!</p>
        <div style='display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;'>
            <div style='background-color: #0e1117; padding: 15px; border-radius: 8px;'>
                <strong style='color: #4a90e2;'>⚡ GPU Acceleration</strong>
                <p style='color: #718096; margin-top: 5px;'>10x faster processing</p>
            </div>
            <div style='background-color: #0e1117; padding: 15px; border-radius: 8px;'>
                <strong style='color: #4a90e2;'>👥 Team Collaboration</strong>
                <p style='color: #718096; margin-top: 5px;'>Share insights instantly</p>
            </div>
            <div style='background-color: #0e1117; padding: 15px; border-radius: 8px;'>
                <strong style='color: #4a90e2;'>💾 Persistent Storage</strong>
                <p style='color: #718096; margin-top: 5px;'>Your data, always available</p>
            </div>
            <div style='background-color: #0e1117; padding: 15px; border-radius: 8px;'>
                <strong style='color: #4a90e2;'>🔌 API Access</strong>
                <p style='color: #718096; margin-top: 5px;'>Integrate anywhere</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Sidebar with better organization
with st.sidebar:
    # Mode indicator
    if deployment_mode == "LOCAL":
        st.markdown("""
        <div style='background-color: #48bb78; color: white; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 20px;'>
            <strong>🏠 LOCAL MODE ACTIVE</strong>
        </div>
        """, unsafe_allow_html=True)
    
    # AI Engine Status with better styling
    st.markdown("### 🤖 AI Engine Status")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            st.success("✅ Ollama is running")
            # Show available models
            try:
                models = response.json().get('models', [])
                if models:
                    with st.expander("Available Models", expanded=False):
                        for model in models:
                            st.text(f"• {model.get('name', 'Unknown')}")
            except:
                pass
        else:
            st.error("❌ Ollama is not responding")
    except:
        st.error("❌ Ollama is not running")
        st.markdown("""
        <div style='background-color: #1a1f2e; padding: 10px; border-radius: 8px; margin-top: 10px;'>
            <code>ollama serve</code>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Data Source Section
    st.markdown("### 📁 Data Source")
    
    data_source = st.radio(
        "Choose your data:",
        ["📤 Upload CSV File", "🔗 Google Sheets URL"],
        index=0,
        label_visibility="collapsed"
    )
    
    data_path = None
    
    if data_source == "📤 Upload CSV File":
        uploaded_file = st.file_uploader(
            "Drop your CSV here",
            type=['csv'],
            help="Supports any CSV format"
        )
        
        if uploaded_file is not None:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                data_path = tmp_file.name
                st.session_state.current_data_source = uploaded_file.name
            
            # Show file info
            file_size = len(uploaded_file.getvalue()) / 1024
            st.info(f"📄 {uploaded_file.name} ({file_size:.1f} KB)")
    
    elif data_source == "🔗 Google Sheets URL":
        sheet_url = st.text_input(
            "Google Sheets URL",
            placeholder="https://docs.google.com/spreadsheets/d/...",
            help="Sheet must be publicly viewable"
        )
        
        if sheet_url:
            data_path = sheet_url
            st.session_state.current_data_source = "Google Sheets"
            st.info("🔗 Google Sheets connected")
    
    # Load data button with better styling
    if data_path:
        if st.button("🚀 Load Data", type="primary", use_container_width=True):
            with st.spinner("Processing your data..."):
                try:
                    # Load the data
                    df = load_client_data(data_path)
                    
                    # Create documents and retriever
                    documents = create_documents(df)
                    retriever = get_retriever(data_path)
                    
                    # Store in session state
                    st.session_state.retriever = retriever
                    st.session_state.data_loaded = True
                    st.session_state.messages = []  # Clear previous messages
                    
                    st.success(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
                    
                    # Show data preview with better formatting
                    with st.expander("📊 Data Preview", expanded=True):
                        st.dataframe(
                            df.head(10),
                            use_container_width=True,
                            hide_index=True
                        )
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Sample questions with better organization
    if st.session_state.data_loaded:
        st.markdown("---")
        st.markdown("### 💡 Quick Questions")
        st.markdown("Try these to get started:")
        
        sample_questions = [
            "What are the main patterns in this data?",
            "Summarize the key insights",
            "Show me statistical summary",
            "What are the unique values?",
            "Find correlations in the data"
        ]
        
        for i, question in enumerate(sample_questions):
            if st.button(
                question,
                key=f"sample_{i}",
                use_container_width=True,
                help="Click to ask this question"
            ):
                st.session_state.messages.append({"role": "user", "content": question})
                st.session_state.pending_question = question  # Mark question as pending
                st.rerun()

# Main chat interface
if st.session_state.data_loaded:
    # Status indicator
    st.markdown(f"""
    <div style='background-color: #1a1f2e; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #48bb78;'>
        <span style='color: #48bb78; font-size: 16px;'>● Connected to: {st.session_state.current_data_source}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Chat messages container
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
    
    # Process pending question from quick questions ONLY
    if hasattr(st.session_state, 'pending_question') and st.session_state.pending_question:
        prompt = st.session_state.pending_question
        st.session_state.pending_question = None  # Clear pending question
        
        # Process the pending question
        process_question = True
    else:
        # Chat input at the bottom
        prompt = st.chat_input("Ask anything about your data...", key="chat_input")
        process_question = bool(prompt)
    
    # Process the prompt
    if process_question and prompt:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display in the chat container
        with chat_container:
            with st.chat_message("user"):
                st.write(prompt)
        
        # Generate response
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    try:
                        # Set up the QA chain
                        llm = ChatOllama(model="llama3.2", temperature=0.7)
                        
                        system_prompt = (
                            "You are a helpful data analyst assistant. "
                            "Use the retrieved context to answer questions accurately. "
                            "If you don't know something, say so. "
                            "Format your responses clearly with bullet points or tables when appropriate. "
                            "Be concise but thorough."
                            "\n\nContext:\n{context}"
                        )
                        
                        prompt_template = ChatPromptTemplate.from_messages([
                            ("system", system_prompt),
                            ("human", "{input}"),
                        ])
                        
                        question_answer_chain = create_stuff_documents_chain(llm, prompt_template)
                        rag_chain = create_retrieval_chain(st.session_state.retriever, question_answer_chain)
                        
                        # Get response
                        response = rag_chain.invoke({"input": prompt})
                        answer = response["answer"]
                        
                        # Display response
                        st.write(answer)
                        
                        # Show source documents in a cleaner way
                        if "context" in response and response["context"]:
                            with st.expander("📄 View Source Data", expanded=False):
                                for i, doc in enumerate(response["context"][:3]):  # Limit to 3
                                    st.markdown(f"**Source {i+1}:**")
                                    st.code(doc.page_content, language="text")
                        
                        # Add assistant message to history
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        with st.expander("💡 Troubleshooting"):
                            st.markdown("""
                            1. **Check Ollama**: Make sure it's running (`ollama serve`)
                            2. **Check Models**: Ensure you have `llama3.2` and `mxbai-embed-large`
                            3. **Memory**: Close other applications if running out of memory
                            """)

else:
    # Welcome screen with better design
    st.markdown("""
    <div style='text-align: center; padding: 40px;'>
        <h2 style='color: #3182ce; margin-bottom: 30px;'>Welcome! Let's analyze your data together.</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Feature cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class='feature-card'>
            <h3 style='color: #48bb78;'>🏠 Local & Private</h3>
            <p style='color: #a0aec0;'>Your data never leaves your computer. Complete privacy guaranteed.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class='feature-card'>
            <h3 style='color: #4299e1;'>🤖 AI-Powered</h3>
            <p style='color: #a0aec0;'>Advanced language models understand your questions naturally.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class='feature-card'>
            <h3 style='color: #ed8936;'>⚡ Instant Insights</h3>
            <p style='color: #a0aec0;'>Get answers in seconds, not hours. No SQL required.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Getting started guide
    st.markdown("""
    <div style='background-color: #1a1f2e; padding: 30px; border-radius: 10px; margin-top: 40px;'>
        <h3 style='text-align: center; color: #e2e8f0; margin-bottom: 20px;'>🚀 Getting Started</h3>
        <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; text-align: center;'>
            <div>
                <div style='background-color: #3182ce; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px;'>1</div>
                <p style='color: #a0aec0;'>Upload your CSV or connect Google Sheets</p>
            </div>
            <div>
                <div style='background-color: #3182ce; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px;'>2</div>
                <p style='color: #a0aec0;'>Click "Load Data" to process</p>
            </div>
            <div>
                <div style='background-color: #3182ce; color: white; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px;'>3</div>
                <p style='color: #a0aec0;'>Start asking questions!</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown(
    "<center style='color: #718096;'>Built with Streamlit and LangChain | Powered by Ollama</center>",
    unsafe_allow_html=True
)