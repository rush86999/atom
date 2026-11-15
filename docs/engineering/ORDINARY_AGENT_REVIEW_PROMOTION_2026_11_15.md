# Ordinary agent creation and reviewed promotion controls

This regression exercises a newly created agent through the public custom-creation, qualification-request, approval and graduation-promotion HTTP routes using synthetic users and JWTs. A fresh database session checks the created agent, the approved review action, reviewer and evidence references, qualification receipt, and linked promotion history. A second created agent with the same fixture evidence remains a student without a qualification receipt; a foreign supervisor receives 404.

The test uses directly inserted synthetic execution, episode and training evidence rows. It establishes controlled policy and persistence behavior, not ordinary training producers, learned capability, real human assessment, live model quality, skills consumption, app restart or browser readiness. It does not change promotion policy or bypass qualification. The original 143 claims and 18 goals remain the completion scope.

Run from backend in an isolated TESTING=1 scratch environment:

```sh
python -m pytest tests/test_goal6_ordinary_creation_positive.py tests/api/test_graduation_qualification_join.py tests/test_graduation_exam_boundary.py tests/test_graduation_qualification_binding.py -q
```

The new regression joins the existing scoped graduation qualification and policy CI step. Existing CI selections are preserved. Independent verification results are recorded with the change before publication.

Independent checks on the reviewed test bytes: 71 passed in the joined qualification/exam/binding selection, followed by 629 passed using the shipping test path and CI lane contract. Both checks used fresh scratch environments and kernel-blocked networking, including an actual denied socket preflight. The CI and additions-ledger diff preserves every prior byte except the single added regression selector.
