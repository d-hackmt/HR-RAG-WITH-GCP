"""06 · splitter — chop each document into small, searchable, overlapping
chunks (config.CHUNK_SIZE / CHUNK_OVERLAP)."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from hr_assistant import config



def split_into_chunks(documents):
    """Split documents into small overlapping chunks. Metadata (source,
    policy_category) carries over onto every chunk automatically."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    return text_splitter.split_documents(documents)
