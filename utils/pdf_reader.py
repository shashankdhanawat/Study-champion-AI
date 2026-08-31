import fitz


def read_pdf(file_path):
    try:
        doc = fitz.open(file_path)

        text = ""

        for page in doc:
            text += page.get_text() + "\n"

        doc.close()

        if not text.strip():
            raise ValueError(
                "No readable text was found in the PDF."
            )

        return text.strip()

    except Exception as e:
        raise RuntimeError(
            f"Could not read PDF: {str(e)}"
        )