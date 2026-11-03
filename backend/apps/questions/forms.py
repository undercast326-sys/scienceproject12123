from django import forms


def _split_lines(text):
    return [line.strip() for line in (text or '').splitlines() if line.strip()]


def _to_text(value):
    if value is None:
        return ''
    if isinstance(value, list):
        return '\n'.join(str(item) for item in value)
    return str(value)


class AnswerKeyForm(forms.ModelForm):
    """Admin form for topic tasks and mock questions.

    `options` and `correct_answer` are JSON in the database, but editors type plain
    text: one option per line, and the correct option(s) copied from that list.
    The model's clean() then checks the key fits the question type.
    """
    options = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text='По одному варианту на строку. Для типа «Text answer» оставьте пустым.',
    )
    correct_answer = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text=(
            'Текст правильного варианта, как в списке выше. Для «Multiple choice» — '
            'каждый правильный вариант на отдельной строке. Для «Text answer» — '
            'ожидаемый ответ (регистр не важен).'
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['options'] = _to_text(self.instance.options)
        self.initial['correct_answer'] = _to_text(self.instance.correct_answer)

    def clean(self):
        cleaned = super().clean()
        cleaned['options'] = _split_lines(cleaned.get('options'))
        raw_answer = cleaned.get('correct_answer')
        if raw_answer is not None:
            if cleaned.get('type') == 'multiple':
                cleaned['correct_answer'] = _split_lines(raw_answer)
            else:
                cleaned['correct_answer'] = raw_answer.strip()
        return cleaned
