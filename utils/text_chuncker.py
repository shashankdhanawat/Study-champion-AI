def chunk_text(text, chunk_size=1000, overlap=200):
 chunks = []
 start = 0
 while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
        chunk=chunk.strip() #removing spaces
 return chunks
