# exceptions.py

class LPFValidationError(Exception):
    pass

# class DelimValidationError(Exception):
class DelimValidationError(Exception):
    def __init__(self, errors):
        super().__init__(errors)
        self.errors = errors

class DelimInsertError(Exception):
    pass

class DataAlreadyProcessedError(DelimInsertError):
    pass

