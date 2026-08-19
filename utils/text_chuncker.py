def chunker_text(text, chunk_size=1000, overlap=200):
	"""Split text into overlapping chunks of at most ``chunk_size`` characters."""
	if not isinstance(text, str):
		raise TypeError("text must be a string")
	if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
		raise ValueError("chunk_size must be a positive integer")
	if not isinstance(overlap, int) or isinstance(overlap, bool) or overlap < 0:
		raise ValueError("overlap must be a non-negative integer")
	if overlap >= chunk_size:
		raise ValueError("overlap must be smaller than chunk_size")

	step = chunk_size - overlap
	return [text[start:start + chunk_size] for start in range(0, len(text), step)]