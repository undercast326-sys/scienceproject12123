from django.urls import path

from .views import StartQuizView, SubmitAnswerView, FinishQuizView

urlpatterns = [
    path('start/', StartQuizView.as_view(), name='quiz-start'),
    path('<int:session_id>/submit-answer/', SubmitAnswerView.as_view(), name='quiz-submit-answer'),
    path('<int:session_id>/finish/', FinishQuizView.as_view(), name='quiz-finish'),
]
