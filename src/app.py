import streamlit as st
import pandas as pd
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from vector import get_retriever, load_client_data, create_documents
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

# Page config
st.set_page_config(
    page_title="Spreadsheet Q&A",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, modern CSS
st.markdown("""
<style>
    /* Hide Streamlit defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Dark theme */
    .stApp {
        background-color: #0a0a0a;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #111111;
        width: 300px;
    }
    
    section[data-testid="stSidebar"] > div {
        padding-top: 2rem;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-weight: 600;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #3b82f6;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: all 0.2s;
        width: 100%;
    }
    
    .stButton > button:hover {
        background-color: #2563eb;
    }
    
    /* Chat */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 0.5rem;
    }
    
    div[data-testid="stChatInput"] {
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        padding-top: 1rem;
    }
    
    /* File uploader */
    [data-testid="stFileUploadDropzone"] {
        background-color: rgba(255, 255, 255, 0.02);
        border: 2px dashed rgba(255, 255, 255, 0.1);
        border-radius: 0.5rem;
    }
    
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #3b82f6;
        background-color: rgba(59, 130, 246, 0.05);
    }
    
    /* Radio buttons */
    .stRadio > div {
        display: flex;
        gap: 1rem;
    }
    
    /* Success/Error messages */
    .stSuccess, .stError, .stInfo {
        padding: 0.75rem 1rem;
        border-radius: 0.375rem;
        margin: 0.5rem 0;
    }
    
    /* Hide deployment mode if not needed */
    div[data-testid="stRadio"] {
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'retriever' not in st.session_state:
    st.session_state.retriever = None
if 'current_source' not in st.session_state:
    st.session_state.current_source = None

# Sidebar
with st.sidebar:
    st.markdown("## 📊 Spreadsheet Q&A")
    st.markdown("---")
    
    # System status
    status_container = st.container()
    with status_container:
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=1)
            if response.status_code == 200:
                st.success("✅ AI Engine Ready")
            else:
                st.error("❌ AI Engine Offline")
        except:
            st.error("❌ AI Engine Offline")
            st.caption("Run `ollama serve` to start")
    
    st.markdown("---")
    
    # Data source
    st.markdown("### 📁 Load Your Data")
    
    upload_method = st.radio(
        "Choose input method:",
        ["Upload CSV", "Google Sheets URL"],
        label_visibility="collapsed"
    )
    
    data_path = None
    
    if upload_method == "Upload CSV":
        uploaded_file = st.file_uploader(
            "Drop your CSV file here",
            type=['csv'],
            label_visibility="collapsed"
        )
        
        if uploaded_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                tmp.write(uploaded_file.getvalue())
                data_path = tmp.name
                st.session_state.current_source = uploaded_file.name
    
    else:  # Google Sheets
        sheet_url = st.text_input(
            "Paste Google Sheets URL",
            placeholder="https://docs.google.com/spreadsheets/d/...",
            label_visibility="collapsed"
        )
        if sheet_url:
            data_path = sheet_url
            st.session_state.current_source = "Google Sheets"
    
    # Load button
    if data_path and not st.session_state.data_loaded:
        if st.button("🚀 Load Data", type="primary"):
            with st.spinner("Processing..."):
                try:
                    df = load_client_data(data_path)
                    documents = create_documents(df)
                    st.session_state.retriever = get_retriever(data_path)
                    st.session_state.data_loaded = True
                    st.session_state.messages = []
                    st.success(f"Loaded {len(df)} rows")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    # Quick actions
    if st.session_state.data_loaded:
        st.markdown("---")
        st.markdown("### 💡 Quick Questions")
        
        questions = [
            "What are the main patterns?",
            "Summarize key insights",
            "Show statistical summary",
            "Find unique values",
            "Identify correlations"
        ]
        
        for q in questions:
            if st.button(q, key=f"q_{q}"):
                st.session_state.messages.append({"role": "user", "content": q})
                st.rerun()

# Main area
if not st.session_state.data_loaded:
    # Welcome screen
    st.markdown("""
    <div style='text-align: center; padding: 3rem 0;'>
        <h1 style='font-size: 3rem; margin-bottom: 1rem;'>Welcome to Spreadsheet Q&A</h1>
        <p style='font-size: 1.25rem; color: #888; margin-bottom: 3rem;'>
            Ask questions about your data in plain English. Get instant AI-powered insights.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 🔒 Private & Secure
        Your data never leaves your computer. Everything runs locally.
        """)
    
    with col2:
        st.markdown("""
        ### 🚀 Instant Analysis
        Get answers in seconds. No SQL or coding required.
        """)
    
    with col3:
        st.markdown("""
        ### 🤖 AI-Powered
        Advanced language models understand your questions naturally.
        """)
    
    st.markdown("""
    <div style='text-align: center; margin-top: 3rem;'>
        <p style='color: #888;'>← Upload your data from the sidebar to get started</p>
    </div>
    """, unsafe_allow_html=True)

else:
    # Chat interface
    st.markdown(f"""
    <div style='display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;'>
        <span style='background: #10b981; width: 8px; height: 8px; border-radius: 50%; display: inline-block;'></span>
        <span style='color: #888;'>Connected to: {st.session_state.current_source}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask anything about your data..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.write(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    llm = ChatOllama(model="llama3.2", temperature=0.7)
                    
                    system_prompt = """You are a helpful data analyst assistant. 
                    Use the retrieved context to answer questions accurately. 
                    If you don't know something, say so. 
                    Format your responses clearly with bullet points or tables when appropriate.
                    Be concise but thorough.
                    
                    Context: {context}"""
                    
                    prompt_template = ChatPromptTemplate.from_messages([
                        ("system", system_prompt),
                        ("human", "{input}"),
                    ])
                    
                    qa_chain = create_stuff_documents_chain(llm, prompt_template)
                    rag_chain = create_retrieval_chain(st.session_state.retriever, qa_chain)
                    
                    response = rag_chain.invoke({"input": prompt})
                    answer = response["answer"]
                    
                    st.write(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    
                    # Source documents (collapsed by default)
                    if "context" in response and response["context"]:
                        with st.expander("View sources"):
                            for i, doc in enumerate(response["context"][:3]):
                                st.text(f"Source {i+1}:\n{doc.page_content[:200]}...")
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.info("Make sure Ollama is running with `ollama serve`")