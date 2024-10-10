from flask import Flask, request, jsonify, render_template
import os
import tempfile
import pdfplumber
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA

app = Flask(__name__)

# Set your GROQ API Key
GROQ_API_KEY = "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"
vectordb = None  # Global variable for vector database


# Function to process the PDF, generate embeddings, and setup vector database
def process_pdf(file_obj):
    try:
        # Save the uploaded PDF file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(file_obj.read())
            temp_pdf.flush()

            # Use pdfplumber to extract text from PDF
            with pdfplumber.open(temp_pdf.name) as pdf:
                documents = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        # Append each page's text as a document in the format required by the splitter
                        documents.append({'content': text})

            if not documents:
                return "No text could be extracted from the PDF.", None

            # Split the text into chunks
            text_splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=50)
            texts = text_splitter.split_documents(documents)

            if not texts:
                return "No text chunks were generated.", None

            # Generate embeddings using HuggingFace
            embeddings = HuggingFaceEmbeddings()

            # Initialize the Chroma vector database
            global vectordb
            vectordb = Chroma.from_documents(texts, embeddings, persist_directory=".")

            if not vectordb:
                return "Failed to initialize Chroma vector database.", None

            return "PDF processed successfully!", vectordb

    except Exception as e:
        return str(e), None


@app.route('/')
def index():
    return render_template('index.html')


# Route for uploading the PDF via a form
@app.route('/upload', methods=['POST'])
def upload_pdf():
    file = request.files.get('file')

    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Process the uploaded PDF
    message, db = process_pdf(file)

    if db is None:
        return jsonify({'error': message}), 400

    return jsonify({'message': message}), 200


# Route for handling user queries after the PDF is processed
@app.route('/query', methods=['POST'])
def query_pdf():
    global vectordb

    if not vectordb:
        return jsonify({'error': 'No PDF processed or vector database not initialized'}), 400

    user_query = request.json.get('query')

    if not user_query:
        return jsonify({'error': 'No query provided'}), 400

    try:
        # Setup retriever and QA chain
        retriever = vectordb.as_retriever()

        # Initialize the ChatGroq model with the GROQ API key
        llm = ChatGroq(model='Llama3-8b-8192', temperature=0, groq_api_key=GROQ_API_KEY)

        # Create a QA chain for retrieval
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )

        # Query the chain
        response = qa_chain.invoke({"query": user_query})

        return jsonify({
            'result': response['result'],
            'source': response['source_documents'][0].metadata.get('source', 'Unknown Source')
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)