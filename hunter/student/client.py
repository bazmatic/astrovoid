"""A drop-in for the Jev client that answers from the trained student."""
from pathlib import Path
from types import SimpleNamespace
from hunter.jev_pilot import PilotUnavailable
from hunter.student.encoder import encode
from hunter.student.network import InvalidModel, StudentModel
from utils.resource_path import resource_path

MODEL_PATH = resource_path('assets/student/jev_student.npz')


class JevStudentClient:
    def __init__(self, model):
        self.model = model

    async def system_one(self, *, state, questions=None, **_):
        answers = {}
        for name, probabilities in self.model.predict(encode(state)).items():
            choice = max(probabilities, key=probabilities.get)
            answers[name] = SimpleNamespace(choice=choice, confidence=probabilities[choice],
                                            probabilities=probabilities)
        return SimpleNamespace(choices=answers)

    async def aclose(self):
        pass


def load_student_client(path=None):
    path = Path(path or MODEL_PATH)
    if not path.is_file():
        raise PilotUnavailable('missing_model')
    try:
        return JevStudentClient(StudentModel.load(path))
    except InvalidModel:
        raise PilotUnavailable('invalid_model') from None
