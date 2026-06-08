class InputProcessor:

    def process(self, text: str):

        return {
            "original_text": text,
            "clean_text": text.strip()
        }