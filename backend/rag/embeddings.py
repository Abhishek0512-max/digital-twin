import chromadb
from openai import OpenAI

from config import OPENAI_API_KEY, EMBEDDING_MODEL, CHROMA_DIR
from rag.chunker import load_all_chunks

_client = OpenAI(api_key=OPENAI_API_KEY)
_chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))

COLLECTION_NAME = "twin_data"


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings from OpenAI in batch."""
    response = _client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def get_collection():
    return _chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def build_index(force_rebuild: bool = False):
    """Chunk all data, embed, and store in ChromaDB."""
    collection = get_collection()

    if collection.count() > 0 and not force_rebuild:
        print(f"Index already exists with {collection.count()} chunks. Skipping build.")
        return collection

    if force_rebuild:
        _chroma.delete_collection(COLLECTION_NAME)
        collection = get_collection()

    chunks = load_all_chunks()
    if not chunks:
        print("No chunks found. Check data directory.")
        return collection

    texts = [c["text"] for c in chunks]
    sources = [c["source"] for c in chunks]
    sections = [c["section"] for c in chunks]

    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_sources = sources[i : i + batch_size]
        batch_sections = sections[i : i + batch_size]
        embeddings = get_embeddings(batch_texts)

        collection.add(
            ids=[f"chunk_{i + j}" for j in range(len(batch_texts))],
            documents=batch_texts,
            embeddings=embeddings,
            metadatas=[
                {"source": s, "section": sec}
                for s, sec in zip(batch_sources, batch_sections)
            ],
        )

    print(f"Built index with {collection.count()} chunks.")
    return collection
