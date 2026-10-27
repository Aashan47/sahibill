from sahibill.speech.score import cer, disagreement, normalise, threshold_for


def test_cer_ignores_punctuation_and_spacing():
    assert cer("یہ بل درست ہے۔", "یہ  بل درست ہے") == 0.0
    assert cer("abc", "abd") == 1 / 3


def test_disagreement_is_symmetric():
    assert disagreement("کیا یہ بل", "کیا وہ بل") == disagreement("کیا وہ بل", "کیا یہ بل")


def test_threshold_keeps_accepted_cer_under_target():
    dev = [(0.0, 0.02), (0.05, 0.04), (0.2, 0.30), (0.4, 0.5)]
    assert threshold_for(dev, 0.05) == 0.05
    assert threshold_for(dev, 0.01) is None
