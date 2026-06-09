import numpy as np
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain.embeddings import OllamaEmbeddings
from langchain.chains import RetrievalQA
from langchain.llms import Ollama
from langchain.memory import ConversationBufferWindowMemory

repo_root = Path("/workspace/lotr")
embs = OllamaEmbeddings(model="nomic-embed-text")

index_path = repo_root / "repo.index"
paths_path = repo_root / "repo_paths.npy"
index = FAISS.load_local(index_path, embs)
paths = np.load(paths_path, allow_pickle=True)

vectorstore = FAISS(embedding=embs, index=index)

memory = ConversationBufferWindowMemory(k=3)
qa_chain = RetrievalQA.from_chain_type(
    llm=Ollama(model="llama3.1:latest"),
    chain_type="stuff",
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    memory=memory,
)

def ask(question: str):
    return qa_chain({"question": question})["result"]

if __name__ == "__main__":
    while True:
        q = input(">>> ")
        if q.lower() in ("exit", "quit"):
            break
        print(ask(q))import numpy as np
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain.embeddings import OllamaEmbeddings
from langchain.chains import RetrievalQA
from langchain.memory import ConversationBufferWindowMemory

repo_root = Path("/workspace/lotr")
embs = OllamaEmbeddings(model="nomic-embed-text")

index = faiss.read_index("repo.index")
paths = np.load("repo_paths.npy", allow_pickle=True)

vectorstore = FAISS(embedding=embs, index=index, docstore={"path": paths})

qa_chain = RetrievalQA.from_chain_type(
    llm=Ollama(model="llama3.1:latest"),
    chain_type="stuff",
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    print(ask(q))