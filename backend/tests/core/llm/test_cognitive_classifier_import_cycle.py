"""Import-order contract for the BYOK CognitiveClassifier wrapper.

During ``core.llm`` package initialization, the parent package can be missing
the ``cognitive_tier_system`` attribute even though the real submodule is
loaded. The wrapper must resolve the module dynamically and preserve
monkeypatching of the real module's class.
"""
import core.llm
import core.llm.byok_handler as byok_handler
import core.llm.cognitive_tier_system as cognitive_tier_system


def test_wrapper_constructs_without_parent_package_attribute(monkeypatch):
    monkeypatch.delattr(
        core.llm, "cognitive_tier_system", raising=False)

    classifier = byok_handler.CognitiveClassifier()

    assert isinstance(classifier, cognitive_tier_system.CognitiveClassifier)


def test_wrapper_normal_constructor_uses_real_class():
    classifier = byok_handler.CognitiveClassifier()

    assert isinstance(classifier, cognitive_tier_system.CognitiveClassifier)


def test_wrapper_preserves_real_module_class_monkeypatch(monkeypatch):
    class FakeClassifier:
        pass

    monkeypatch.setattr(
        cognitive_tier_system, "CognitiveClassifier", FakeClassifier)
    monkeypatch.delattr(
        core.llm, "cognitive_tier_system", raising=False)

    classifier = byok_handler.CognitiveClassifier()

    assert isinstance(classifier, FakeClassifier)
