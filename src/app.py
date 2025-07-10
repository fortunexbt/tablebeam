import streamlit as st
import tempfile
from pathlib import Path
import sys
import os

# Add parent directory to path to import local modules
sys.path.append(str(Path(__file__).parent))

# Lazy imports to speed up initial load
def get_imports():
    global pd, get_retriever, load_client_data, create_documents
    global create_retrieval_chain, create_stuff_documents_chain
    global ChatPromptTemplate, ChatOllama
    
    if 'pd' not in globals():
        import pandas as pd
        from vector import get_retriever, load_client_data, create_documents
        from langchain.chains import create_retrieval_chain
        from langchain.chains.combine_documents import create_stuff_documents_chain
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_ollama import ChatOllama

# Import model selector
from model_selector_v2 import HardwareDetector, ModelRecommender, render_model_settings_ui

# Set page config
st.set_page_config(
    page_title="Spreadsheet Q&A Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional CSS with better colors (not all black)
st.markdown("""
<style>
    /* Main app background - subtle dark */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Sidebar with slight contrast */
    section[data-testid="stSidebar"] {
        background-color: #1a1f2e;
        border-right: 1px solid #2d3748;
    }
    
    /* Feature cards */
    .feature-card {
        background-color: #1a1f2e;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2d3748;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    
    .feature-card:hover {
        border-color: #3182ce;
        transform: translateY(-2px);
    }
    
    /* Quick question pills */
    .quick-question {
        display: inline-block;
        background-color: #2d3748;
        color: #e2e8f0;
        padding: 8px 16px;
        border-radius: 20px;
        margin: 4px;
        cursor: pointer;
        transition: all 0.2s;
        border: 1px solid transparent;
    }
    
    .quick-question:hover {
        background-color: #3182ce;
        border-color: #3182ce;
    }
    
    /* Better button styling */
    .stButton > button {
        background-color: #3182ce;
        color: white;
        border: none;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        background-color: #2563eb;
        transform: translateY(-1px);
    }
    
    /* Chat messages */
    .stChatMessage {
        background-color: rgba(26, 31, 46, 0.6);
        border: 1px solid #2d3748;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    
    /* Status badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background-color: rgba(72, 187, 120, 0.1);
        border: 1px solid #48bb78;
        padding: 8px 16px;
        border-radius: 20px;
        color: #48bb78;
        font-size: 14px;
    }
    
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* File uploader */
    [data-testid="stFileUploadDropzone"] {
        background-color: #1a1f2e;
        border: 2px dashed #2d3748;
        border-radius: 10px;
    }
    
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #3182ce;
    }
    
    /* Text inputs */
    .stTextInput > div > div > input {
        background-color: #1a1f2e;
        border: 1px solid #2d3748;
        color: white;
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
if 'embedding_model' not in st.session_state:
    # Set defaults based on hardware
    detector = HardwareDetector()
    recommender = ModelRecommender(detector.info)
    recommendations = recommender.recommend_models()
    st.session_state.embedding_model = recommendations['embedding']['name']
    st.session_state.llm_model = recommendations['llm']['name']
if 'process_last_message' not in st.session_state:
    st.session_state.process_last_message = False
if 'last_embedding_model' not in st.session_state:
    st.session_state.last_embedding_model = st.session_state.embedding_model
if 'temp_file_path' not in st.session_state:
    st.session_state.temp_file_path = None

# Header
st.markdown("""
<div style='text-align: center; padding: 20px 0 40px 0;'>
    <h1 style='color: #3182ce; margin-bottom: 10px;'>📊 Spreadsheet Q&A Assistant</h1>
    <p style='color: #a0aec0; font-size: 18px;'>Ask questions about your data in natural language</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    # AI Engine Status
    st.markdown("### 🤖 AI Engine Status")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            st.success("✅ Ollama is running")
        else:
            st.error("❌ Ollama is not responding")
    except:
        st.error("❌ Ollama is not running")
        st.code("ollama serve", language="bash")
    
    st.markdown("---")
    
    # Model Settings (collapsible)
    with st.expander("⚙️ Model Settings", expanded=False):
        render_model_settings_ui(st)
    
    st.markdown("---")
    
    # Data Source Section
    st.markdown("### 📁 Data Source")
    
    # Clear Vector Store button (for troubleshooting)
    if st.session_state.data_loaded:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🗑️ Clear Cache", help="Clear vector store if you're having issues"):
                try:
                    import shutil
                    if os.path.exists("./chroma_db_clients/"):
                        shutil.rmtree("./chroma_db_clients/")
                        st.success("✅ Cache cleared")
                        st.session_state.data_loaded = False
                        st.session_state.retriever = None
                        st.session_state.messages = []
                        st.rerun()
                except Exception as e:
                    st.error(f"Error clearing cache: {e}")
    
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
            try:
                # Debug info
                file_size = len(uploaded_file.getvalue())
                st.info(f"📁 Uploaded file: {uploaded_file.name} ({file_size} bytes)")
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='wb') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file.flush()  # Ensure all data is written
                    data_path = tmp_file.name
                    st.session_state.current_data_source = uploaded_file.name
                    st.session_state.temp_file_path = data_path  # Store in session state
                    st.success(f"✅ File saved to: {data_path}")
            except Exception as e:
                st.error(f"❌ Error processing uploaded file: {str(e)}")
                data_path = None
    
    elif data_source == "🔗 Google Sheets URL":
        sheet_url = st.text_input(
            "Google Sheets URL",
            placeholder="https://docs.google.com/spreadsheets/d/...",
            help="Sheet must be publicly viewable"
        )
        
        if sheet_url:
            data_path = sheet_url
            st.session_state.current_data_source = "Google Sheets"
    
    # Load data button
    if data_path:
        # Check if embedding model changed
        embedding_model_changed = ('last_embedding_model' in st.session_state and 
                                   st.session_state.last_embedding_model != st.session_state.embedding_model)
        
        if embedding_model_changed and st.session_state.data_loaded:
            st.warning("⚠️ Embedding model changed. Please reload your data to apply the new model.")
        
        if st.button("🚀 Load Data", type="primary", use_container_width=True):
            with st.spinner("Processing your data..."):
                try:
                    get_imports()  # Load heavy imports only when needed
                    
                    # Step 1: Load data
                    with st.spinner("Loading CSV data..."):
                        df = load_client_data(data_path)
                        st.info(f"📊 Loaded {len(df)} rows, {len(df.columns)} columns")
                    
                    # Step 2: Create documents
                    with st.spinner("Creating searchable documents..."):
                        documents = create_documents(df)
                        st.info(f"📄 Created {len(documents)} documents")
                    
                    # Step 3: Create retriever
                    with st.spinner("Building vector index..."):
                        retriever = get_retriever(data_path, embedding_model=st.session_state.embedding_model)
                    
                    st.session_state.retriever = retriever
                    st.session_state.data_loaded = True
                    st.session_state.messages = []
                    st.session_state.last_embedding_model = st.session_state.embedding_model
                    
                    st.success(f"✅ Successfully loaded {len(df)} rows, {len(df.columns)} columns")
                    
                    with st.expander("📊 Data Preview", expanded=False):
                        st.dataframe(df.head(10), use_container_width=True, hide_index=True)
                    
                except Exception as e:
                    st.error(f"❌ Error loading data: {str(e)}")
                    import traceback
                    with st.expander("🔍 Error Details"):
                        st.code(traceback.format_exc())

# Main chat interface
if st.session_state.data_loaded:
    # Status indicator
    st.markdown(f"""
    <div class='status-badge'>
        <span style='width: 8px; height: 8px; background: #48bb78; border-radius: 50%; display: inline-block;'></span>
        Connected to: {st.session_state.current_data_source}
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Quick questions in the main area (not sidebar!)
    st.markdown("#### 💡 Quick Questions")
    quick_questions = [
        "What are the main patterns in this data?",
        "Summarize the key insights",
        "Show me statistical summary",
        "What are the unique values?",
        "Find correlations in the data"
    ]
    
    # Create columns for quick question buttons
    cols = st.columns(3)
    for i, question in enumerate(quick_questions):
        with cols[i % 3]:
            if st.button(question, key=f"quick_{i}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": question})
                st.session_state.process_last_message = True
                st.rerun()
    
    st.markdown("---")
    
    # Chat messages container
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
    
    # Process last message if triggered by quick question
    if st.session_state.process_last_message and st.session_state.messages:
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "user":
            st.session_state.process_last_message = False
            prompt = last_message["content"]
            
            # Generate and display response
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing..."):
                        try:
                            get_imports()  # Ensure imports are loaded
                            # Set up the QA chain with selected model
                            llm = ChatOllama(model=st.session_state.llm_model, temperature=0.7)
                            
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
                                    for i, doc in enumerate(response["context"][:3]):
                                        st.markdown(f"**Source {i+1}:**")
                                        st.code(doc.page_content, language="text")
                            
                            # Add assistant message to history
                            st.session_state.messages.append({"role": "assistant", "content": answer})
                            
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                            with st.expander("💡 Troubleshooting"):
                                st.markdown("""
                                1. **Check Ollama**: Make sure it's running (`ollama serve`)
                                2. **Check Models**: Ensure you have the selected models installed
                                3. **Memory**: Close other applications if running out of memory
                                4. **Embedding Model**: If you changed the embedding model, reload your data
                                """)
    
    # Chat input at the bottom
    if prompt := st.chat_input("Ask anything about your data...", key="chat_input"):
        # Add user message to history and process
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.write(prompt)
        
        # Generate and display response
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    try:
                        get_imports()  # Ensure imports are loaded
                        # Set up the QA chain with selected model
                        llm = ChatOllama(model=st.session_state.llm_model, temperature=0.7)
                        
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
                                for i, doc in enumerate(response["context"][:3]):
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
    # Welcome screen
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