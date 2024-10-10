import streamlit as st
import tempfile
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA

# Set your GROQ API Key directly in the code
GROQ_API_KEY = "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"

# Initialize global variable for vector database
vectordb = None

# Function to process the PDF, generate embeddings, and set up the vector database
def process_pdf(file_obj):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(file_obj.read())
            temp_pdf.flush()

            loader = UnstructuredPDFLoader(temp_pdf.name)
            documents = loader.load()

            if not documents:
                st.error("No documents loaded from the PDF.")
                return None

            text_splitter = CharacterTextSplitter(chunk_size=800, chunk_overlap=50)
            texts = text_splitter.split_documents(documents)

            if not texts:
                st.error("No text chunks were generated.")
                return None

            embeddings = HuggingFaceEmbeddings()

            global vectordb
            vectordb = Chroma.from_documents(texts, embeddings, persist_directory=".")

            if not vectordb:
                st.error("Failed to initialize Chroma vector DB.")
                return None

            st.success("PDF processed successfully!")
            return vectordb

    except Exception as e:
        st.error(f"Error processing PDF: {e}")
        return None

# Main Streamlit app
def main():
    st.title("PDF Processing and Querying with LLM")

    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")
    
    if uploaded_file is not None:
        st.info("Processing the PDF... Please wait.")
        if process_pdf(uploaded_file):
            st.success("PDF processed successfully!")
        else:
            st.error("Failed to process the PDF. Please try again.")

    user_query = st.text_input("Ask a question about the PDF:")
    
    if st.button("Submit Query"):
        if not vectordb:
            st.error("Please upload and process a PDF before querying.")
        elif not user_query:
            st.error("Please enter a query.")
        else:
            try:
                retriever = vectordb.as_retriever()

                # Pass the GROQ API key directly when creating the ChatGroq instance
                llm = ChatGroq(model='Llama3-8b-8192', temperature=0, groq_api_key=GROQ_API_KEY)

                qa_chain = RetrievalQA.from_chain_type(
                    llm=llm,
                    chain_type="stuff",
                    retriever=retriever,
                    return_source_documents=True
                )

                response = qa_chain.invoke({"query": user_query})

                st.write("### Result:")
                st.write(response['result'])
                
                if response.get('source_documents'):
                    st.write("### Source Document:")
                    st.write(response['source_documents'][0].metadata.get('source', 'Unknown Source'))
                else:
                    st.warning("No source documents found.")

            except Exception as e:
                st.error(f"Error during query: {e}")

if __name__ == "__main__":
    main()
