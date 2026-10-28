# Проверка текстов (колонки 13, 14, 16)

Правила — `prompts/validate_fields.md`. Автоматические блоки считает `src/validation.py` при `python run.py`; блоки а, б и подстановку чисел в пример проверяет человек или агент и записывает в `data/review/validation_review.yaml`.


## Охват

| Тип | Записей | С текстами | Без текстов |
|---|---|---|---|
| метрика | 19 | 19 | 0 |
| термин | 164 | 115 | 49 |


## Итог по блокам (доля записей без замечаний)

| Блок | Метрики | Термины |
|---|---|---|
| Формат: объём, слова, формулы и условный пример | 100% (19 из 19) | 100% (115 из 115) |
| а) Утверждения опираются на источники | 100% (19 из 19) | 30% (35 из 115) |
| б) Короткое определение не противоречит длинному и источникам | 100% (19 из 19) | 30% (35 из 115) |
| в) Формула сходится с определением | 100% (19 из 19) | 30% (35 из 115) |
| г) Нет направления «Ниже/Выше — лучше» | 100% (19 из 19) | 100% (115 из 115) |
| д) Записи из источника есть в «Связанных терминах» | 100% (19 из 19) | 100% (115 из 115) |


Записей с замечаниями: 80 из 134; замечаний всего: 240.


## Список правок

| Запись | Блок | Замечание |
|---|---|---|
| biometric-data-subject | a | ревью нет (хэш d353e4518d4c) |
| biometric-data-subject | b | ревью нет (хэш d353e4518d4c) |
| biometric-data-subject | c | ревью нет (хэш d353e4518d4c) |
| biometric-data | a | ревью нет (хэш d256762342af) |
| biometric-data | b | ревью нет (хэш d256762342af) |
| biometric-data | c | ревью нет (хэш d256762342af) |
| biometric-database | a | ревью нет (хэш f34fc694f65c) |
| biometric-database | b | ревью нет (хэш f34fc694f65c) |
| biometric-database | c | ревью нет (хэш f34fc694f65c) |
| biometric-enrollee | a | ревью нет (хэш c0b39b2e1c0f) |
| biometric-enrollee | b | ревью нет (хэш c0b39b2e1c0f) |
| biometric-enrollee | c | ревью нет (хэш c0b39b2e1c0f) |
| biometric-enrolment-data-record | a | ревью нет (хэш a15ffdeca7bf) |
| biometric-enrolment-data-record | b | ревью нет (хэш a15ffdeca7bf) |
| biometric-enrolment-data-record | c | ревью нет (хэш a15ffdeca7bf) |
| biometric-enrolment-database | a | ревью нет (хэш d8653725b5de) |
| biometric-enrolment-database | b | ревью нет (хэш d8653725b5de) |
| biometric-enrolment-database | c | ревью нет (хэш d8653725b5de) |
| biometric-enrolment | a | ревью нет (хэш c648062fb2a6) |
| biometric-enrolment | b | ревью нет (хэш c648062fb2a6) |
| biometric-enrolment | c | ревью нет (хэш c648062fb2a6) |
| biometric-false-acceptance | a | ревью нет (хэш f9137cf461db) |
| biometric-false-acceptance | b | ревью нет (хэш f9137cf461db) |
| biometric-false-acceptance | c | ревью нет (хэш f9137cf461db) |
| biometric-false-rejection | a | ревью нет (хэш 4e3474fe20e2) |
| biometric-false-rejection | b | ревью нет (хэш 4e3474fe20e2) |
| biometric-false-rejection | c | ревью нет (хэш 4e3474fe20e2) |
| biometric-feature-extraction | a | ревью нет (хэш 61f98c8c3bae) |
| biometric-feature-extraction | b | ревью нет (хэш 61f98c8c3bae) |
| biometric-feature-extraction | c | ревью нет (хэш 61f98c8c3bae) |
| biometric-feature | a | ревью нет (хэш 3ab70c75b2cc) |
| biometric-feature | b | ревью нет (хэш 3ab70c75b2cc) |
| biometric-feature | c | ревью нет (хэш 3ab70c75b2cc) |
| biometric-identification-decision | a | ревью нет (хэш e5234fe07c3c) |
| biometric-identification-decision | b | ревью нет (хэш e5234fe07c3c) |
| biometric-identification-decision | c | ревью нет (хэш e5234fe07c3c) |
| biometric-identification-system | a | ревью нет (хэш f5a08d03fac8) |
| biometric-identification-system | b | ревью нет (хэш f5a08d03fac8) |
| biometric-identification-system | c | ревью нет (хэш f5a08d03fac8) |
| biometric-identification | a | ревью нет (хэш c2d00fa0f3a7) |
| biometric-identification | b | ревью нет (хэш c2d00fa0f3a7) |
| biometric-identification | c | ревью нет (хэш c2d00fa0f3a7) |
| biometric-mated-comparison-trial | a | ревью нет (хэш 94440e631dbc) |
| biometric-mated-comparison-trial | b | ревью нет (хэш 94440e631dbc) |
| biometric-mated-comparison-trial | c | ревью нет (хэш 94440e631dbc) |
| biometric-model | a | ревью нет (хэш d528b56661a1) |
| biometric-model | b | ревью нет (хэш d528b56661a1) |
| biometric-model | c | ревью нет (хэш d528b56661a1) |
| biometric-non-mated-comparison-trial | a | ревью нет (хэш 47707f43f464) |
| biometric-non-mated-comparison-trial | b | ревью нет (хэш 47707f43f464) |
| biometric-non-mated-comparison-trial | c | ревью нет (хэш 47707f43f464) |
| biometric-operational-personnel | a | ревью нет (хэш 24ca30beb4fe) |
| biometric-operational-personnel | b | ревью нет (хэш 24ca30beb4fe) |
| biometric-operational-personnel | c | ревью нет (хэш 24ca30beb4fe) |
| biometric-presentation | a | ревью нет (хэш cc2eeb40a537) |
| biometric-presentation | b | ревью нет (хэш cc2eeb40a537) |
| biometric-presentation | c | ревью нет (хэш cc2eeb40a537) |
| biometric-probe | a | ревью нет (хэш 9fd8129c6011) |
| biometric-probe | b | ревью нет (хэш 9fd8129c6011) |
| biometric-probe | c | ревью нет (хэш 9fd8129c6011) |
| biometric-property | a | ревью нет (хэш 58355c8c927c) |
| biometric-property | b | ревью нет (хэш 58355c8c927c) |
| biometric-property | c | ревью нет (хэш 58355c8c927c) |
| biometric-recognition | a | ревью нет (хэш 3ecfd03fe69c) |
| biometric-recognition | b | ревью нет (хэш 3ecfd03fe69c) |
| biometric-recognition | c | ревью нет (хэш 3ecfd03fe69c) |
| biometric-reference-adaptation | a | ревью нет (хэш 078011ee4832) |
| biometric-reference-adaptation | b | ревью нет (хэш 078011ee4832) |
| biometric-reference-adaptation | c | ревью нет (хэш 078011ee4832) |
| biometric-reference-data-record | a | ревью нет (хэш d53e544cd0b0) |
| biometric-reference-data-record | b | ревью нет (хэш d53e544cd0b0) |
| biometric-reference-data-record | c | ревью нет (хэш d53e544cd0b0) |
| biometric-reference-database | a | ревью нет (хэш 3266289a9894) |
| biometric-reference-database | b | ревью нет (хэш 3266289a9894) |
| biometric-reference-database | c | ревью нет (хэш 3266289a9894) |
| biometric-reference-identifier | a | ревью нет (хэш 4abd4846a748) |
| biometric-reference-identifier | b | ревью нет (хэш 4abd4846a748) |
| biometric-reference-identifier | c | ревью нет (хэш 4abd4846a748) |
| biometric-reference | a | ревью нет (хэш b38ff72b3be3) |
| biometric-reference | b | ревью нет (хэш b38ff72b3be3) |
| biometric-reference | c | ревью нет (хэш b38ff72b3be3) |
| biometric-representation | a | ревью нет (хэш 864fb6c11db0) |
| biometric-representation | b | ревью нет (хэш 864fb6c11db0) |
| biometric-representation | c | ревью нет (хэш 864fb6c11db0) |
| biometric-sample | a | ревью нет (хэш ba09cd8116f9) |
| biometric-sample | b | ревью нет (хэш ba09cd8116f9) |
| biometric-sample | c | ревью нет (хэш ba09cd8116f9) |
| biometric-search | a | ревью нет (хэш 89addd992f9d) |
| biometric-search | b | ревью нет (хэш 89addd992f9d) |
| biometric-search | c | ревью нет (хэш 89addd992f9d) |
| biometric-system-operator | a | ревью нет (хэш 8ecdee4e473d) |
| biometric-system-operator | b | ревью нет (хэш 8ecdee4e473d) |
| biometric-system-operator | c | ревью нет (хэш 8ecdee4e473d) |
| biometric-system-owner | a | ревью нет (хэш bb4e0867bf8d) |
| biometric-system-owner | b | ревью нет (хэш bb4e0867bf8d) |
| biometric-system-owner | c | ревью нет (хэш bb4e0867bf8d) |
| biometric-system | a | ревью нет (хэш fd65e57511ee) |
| biometric-system | b | ревью нет (хэш fd65e57511ee) |
| biometric-system | c | ревью нет (хэш fd65e57511ee) |
| biometric-template | a | ревью нет (хэш 4d46f32ace22) |
| biometric-template | b | ревью нет (хэш 4d46f32ace22) |
| biometric-template | c | ревью нет (хэш 4d46f32ace22) |
| biometric-verification-decision | a | ревью нет (хэш 974b485d3b5d) |
| biometric-verification-decision | b | ревью нет (хэш 974b485d3b5d) |
| biometric-verification-decision | c | ревью нет (хэш 974b485d3b5d) |
| biometric-verification-system | a | ревью нет (хэш b9b4f58753cc) |
| biometric-verification-system | b | ревью нет (хэш b9b4f58753cc) |
| biometric-verification-system | c | ревью нет (хэш b9b4f58753cc) |
| biometric-verification | a | ревью нет (хэш da4224de4b4d) |
| biometric-verification | b | ревью нет (хэш da4224de4b4d) |
| biometric-verification | c | ревью нет (хэш da4224de4b4d) |
| biometric | a | ревью нет (хэш a757890b6747) |
| biometric | b | ревью нет (хэш a757890b6747) |
| biometric | c | ревью нет (хэш a757890b6747) |
| bona-fide-presentation | a | ревью нет (хэш 3556b3721594) |
| bona-fide-presentation | b | ревью нет (хэш 3556b3721594) |
| bona-fide-presentation | c | ревью нет (хэш 3556b3721594) |
| capture-attempt | a | ревью нет (хэш 0f67370d1128) |
| capture-attempt | b | ревью нет (хэш 0f67370d1128) |
| capture-attempt | c | ревью нет (хэш 0f67370d1128) |
| capture-task | a | ревью нет (хэш 8ed14a048b0c) |
| capture-task | b | ревью нет (хэш 8ed14a048b0c) |
| capture-task | c | ревью нет (хэш 8ed14a048b0c) |
| capture-transaction | a | ревью нет (хэш 5163f5e3dfb0) |
| capture-transaction | b | ревью нет (хэш 5163f5e3dfb0) |
| capture-transaction | c | ревью нет (хэш 5163f5e3dfb0) |
| captured-biometric-sample | a | ревью нет (хэш 8c2050bc5234) |
| captured-biometric-sample | b | ревью нет (хэш 8c2050bc5234) |
| captured-biometric-sample | c | ревью нет (хэш 8c2050bc5234) |
| channel-effect | a | ревью нет (хэш 95db7c0e4fd9) |
| channel-effect | b | ревью нет (хэш 95db7c0e4fd9) |
| channel-effect | c | ревью нет (хэш 95db7c0e4fd9) |
| claimant | a | ревью нет (хэш 6829222132b0) |
| claimant | b | ревью нет (хэш 6829222132b0) |
| claimant | c | ревью нет (хэш 6829222132b0) |
| closed-set-test | a | ревью нет (хэш b2aafa5d335b) |
| closed-set-test | b | ревью нет (хэш b2aafa5d335b) |
| closed-set-test | c | ревью нет (хэш b2aafa5d335b) |
| cognizant-presentation | a | ревью нет (хэш c764ba6d6fc3) |
| cognizant-presentation | b | ревью нет (хэш c764ba6d6fc3) |
| cognizant-presentation | c | ревью нет (хэш c764ba6d6fc3) |
| comparison-decision | a | ревью нет (хэш aba13c978a3a) |
| comparison-decision | b | ревью нет (хэш aba13c978a3a) |
| comparison-decision | c | ревью нет (хэш aba13c978a3a) |
| comparison-score | a | ревью нет (хэш 0a534d0492e1) |
| comparison-score | b | ревью нет (хэш 0a534d0492e1) |
| comparison-score | c | ревью нет (хэш 0a534d0492e1) |
| comparison-trial | a | ревью нет (хэш 54e104604ebb) |
| comparison-trial | b | ревью нет (хэш 54e104604ebb) |
| comparison-trial | c | ревью нет (хэш 54e104604ebb) |
| comparison | a | ревью нет (хэш 24d45d183d0e) |
| comparison | b | ревью нет (хэш 24d45d183d0e) |
| comparison | c | ревью нет (хэш 24d45d183d0e) |
| computational-workload | a | ревью нет (хэш cb1df0f7b408) |
| computational-workload | b | ревью нет (хэш cb1df0f7b408) |
| computational-workload | c | ревью нет (хэш cb1df0f7b408) |
| conformant-capture-attempt | a | ревью нет (хэш febb27c79e44) |
| conformant-capture-attempt | b | ревью нет (хэш febb27c79e44) |
| conformant-capture-attempt | c | ревью нет (хэш febb27c79e44) |
| cooperative-biometric-capture-subject | a | ревью нет (хэш 2034de0175ae) |
| cooperative-biometric-capture-subject | b | ревью нет (хэш 2034de0175ae) |
| cooperative-biometric-capture-subject | c | ревью нет (хэш 2034de0175ae) |
| cooperative-presentation | a | ревью нет (хэш 21ecd588e228) |
| cooperative-presentation | b | ревью нет (хэш 21ecd588e228) |
| cooperative-presentation | c | ревью нет (хэш 21ecd588e228) |
| cumulative-match-characteristic-plot | a | ревью нет (хэш 62ce79023ccc) |
| cumulative-match-characteristic-plot | b | ревью нет (хэш 62ce79023ccc) |
| cumulative-match-characteristic-plot | c | ревью нет (хэш 62ce79023ccc) |
| dissimilarity-score | a | ревью нет (хэш 9049f2feb248) |
| dissimilarity-score | b | ревью нет (хэш 9049f2feb248) |
| dissimilarity-score | c | ревью нет (хэш 9049f2feb248) |
| duplicate-biometric-enrolment-check | a | ревью нет (хэш 527cf1320e30) |
| duplicate-biometric-enrolment-check | b | ревью нет (хэш 527cf1320e30) |
| duplicate-biometric-enrolment-check | c | ревью нет (хэш 527cf1320e30) |
| enrol | a | ревью нет (хэш c8b4084fda4c) |
| enrol | b | ревью нет (хэш c8b4084fda4c) |
| enrol | c | ревью нет (хэш c8b4084fda4c) |
| enrolment-attempt | a | ревью нет (хэш fd5f29bba771) |
| enrolment-attempt | b | ревью нет (хэш fd5f29bba771) |
| enrolment-attempt | c | ревью нет (хэш fd5f29bba771) |
| enrolment-transaction | a | ревью нет (хэш 689e2e4780bf) |
| enrolment-transaction | b | ревью нет (хэш 689e2e4780bf) |
| enrolment-transaction | c | ревью нет (хэш 689e2e4780bf) |
| experimenter | a | ревью нет (хэш 490c287e9134) |
| experimenter | b | ревью нет (хэш 490c287e9134) |
| experimenter | c | ревью нет (хэш 490c287e9134) |
| failure-to-acquire | a | ревью нет (хэш c040910ee068) |
| failure-to-acquire | b | ревью нет (хэш c040910ee068) |
| failure-to-acquire | c | ревью нет (хэш c040910ee068) |
| failure-to-capture | a | ревью нет (хэш 002a7fcf054b) |
| failure-to-capture | b | ревью нет (хэш 002a7fcf054b) |
| failure-to-capture | c | ревью нет (хэш 002a7fcf054b) |
| failure-to-enrol | a | ревью нет (хэш 89ac2e628745) |
| failure-to-enrol | b | ревью нет (хэш 89ac2e628745) |
| failure-to-enrol | c | ревью нет (хэш 89ac2e628745) |
| false-match | a | ревью нет (хэш ca59f9a4f0d6) |
| false-match | b | ревью нет (хэш ca59f9a4f0d6) |
| false-match | c | ревью нет (хэш ca59f9a4f0d6) |
| false-non-match | a | ревью нет (хэш b0a067521091) |
| false-non-match | b | ревью нет (хэш b0a067521091) |
| false-non-match | c | ревью нет (хэш b0a067521091) |
| filter | a | ревью нет (хэш 18eddf5e89a7) |
| filter | b | ревью нет (хэш 18eddf5e89a7) |
| filter | c | ревью нет (хэш 18eddf5e89a7) |
| fraudulent-biometric-enrolment-data | a | ревью нет (хэш 4c004dee450c) |
| fraudulent-biometric-enrolment-data | b | ревью нет (хэш 4c004dee450c) |
| fraudulent-biometric-enrolment-data | c | ревью нет (хэш 4c004dee450c) |
| full-biometric-system | a | ревью нет (хэш 48af29c2245e) |
| full-biometric-system | b | ревью нет (хэш 48af29c2245e) |
| full-biometric-system | c | ревью нет (хэш 48af29c2245e) |
| identification-transaction | a | ревью нет (хэш b00f2b181f17) |
| identification-transaction | b | ревью нет (хэш b00f2b181f17) |
| identification-transaction | c | ревью нет (хэш b00f2b181f17) |
| identify | a | ревью нет (хэш f143b3732a57) |
| identify | b | ревью нет (хэш f143b3732a57) |
| identify | c | ревью нет (хэш f143b3732a57) |
| identity-concealer | a | ревью нет (хэш bac7f904522d) |
| identity-concealer | b | ревью нет (хэш bac7f904522d) |
| identity-concealer | c | ревью нет (хэш bac7f904522d) |
| impostor | a | ревью нет (хэш 3079552b63e6) |
| impostor | b | ревью нет (хэш 3079552b63e6) |
| impostor | c | ревью нет (хэш 3079552b63e6) |
| indifferent-biometric-capture-subject | a | ревью нет (хэш 6c72d44e739d) |
| indifferent-biometric-capture-subject | b | ревью нет (хэш 6c72d44e739d) |
| indifferent-biometric-capture-subject | c | ревью нет (хэш 6c72d44e739d) |
| indifferent-presentation | a | ревью нет (хэш 0a9230f71504) |
| indifferent-presentation | b | ревью нет (хэш 0a9230f71504) |
| indifferent-presentation | c | ревью нет (хэш 0a9230f71504) |
| intermediate-biometric-sample-processing | a | ревью нет (хэш 8d6bf753c5cc) |
| intermediate-biometric-sample-processing | b | ревью нет (хэш 8d6bf753c5cc) |
| intermediate-biometric-sample-processing | c | ревью нет (хэш 8d6bf753c5cc) |
| intermediate-biometric-sample | a | ревью нет (хэш 711d25d63197) |
| intermediate-biometric-sample | b | ревью нет (хэш 711d25d63197) |
| intermediate-biometric-sample | c | ревью нет (хэш 711d25d63197) |
| liveness-detection | a | ревью нет (хэш 126947ef5a88) |
| liveness-detection | b | ревью нет (хэш 126947ef5a88) |
| liveness-detection | c | ревью нет (хэш 126947ef5a88) |
| liveness | a | ревью нет (хэш c2a48cfa14bd) |
| liveness | b | ревью нет (хэш c2a48cfa14bd) |
| liveness | c | ревью нет (хэш c2a48cfa14bd) |


## По записям

| Запись | Тип | Ревью | f | a | b | c | d | e |
|---|---|---|---|---|---|---|---|---|
| APAR | метрика | проверено | + | + | + | + | + | + |
| APCER | метрика | проверено | + | + | + | + | + | + |
| APNRR | метрика | проверено | + | + | + | + | + | + |
| BPCER | метрика | проверено | + | + | + | + | + | + |
| BPNRR | метрика | проверено | + | + | + | + | + | + |
| CAPNIR | метрика | проверено | + | + | + | + | + | + |
| CAPNMR | метрика | проверено | + | + | + | + | + | + |
| DCS-PD | термин | проверено | + | + | + | + | + | + |
| DET | термин | проверено | + | + | + | + | + | + |
| FAR | метрика | проверено | + | + | + | + | + | + |
| FMR | метрика | проверено | + | + | + | + | + | + |
| FNIR | метрика | проверено | + | + | + | + | + | + |
| FNMR | метрика | проверено | + | + | + | + | + | + |
| FPIR | метрика | проверено | + | + | + | + | + | + |
| FRR | метрика | проверено | + | + | + | + | + | + |
| FS-PD | термин | проверено | + | + | + | + | + | + |
| FTA | метрика | проверено | + | + | + | + | + | + |
| FTE | метрика | проверено | + | + | + | + | + | + |
| IAPAR | метрика | проверено | + | + | + | + | + | + |
| IAPIR | метрика | проверено | + | + | + | + | + | + |
| IAPMR | метрика | проверено | + | + | + | + | + | + |
| IUT | термин | проверено | + | + | + | + | + | + |
| PAD | термин | проверено | + | + | + | + | + | + |
| pai-series | термин | проверено | + | + | + | + | + | + |
| pai-species | термин | проверено | + | + | + | + | + | + |
| PAI | термин | проверено | + | + | + | + | + | + |
| PS-PD | термин | проверено | + | + | + | + | + | + |
| SEL | термин | проверено | + | + | + | + | + | + |
| TOE | термин | проверено | + | + | + | + | + | + |
| TPIR | метрика | проверено | + | + | + | + | + | + |
| acceptable-biometric-capture-attempt | термин | проверено | + | + | + | + | + | + |
| acquire | термин | проверено | + | + | + | + | + | + |
| anonymized-biometric-data-record | термин | проверено | + | + | + | + | + | + |
| artefact | термин | проверено | + | + | + | + | + | + |
| attack-potential | термин | проверено | + | + | + | + | + | + |
| attack-type | термин | проверено | + | + | + | + | + | + |
| authentication | термин | проверено | + | + | + | + | + | + |
| biometric-acquisition-process | термин | проверено | + | + | + | + | + | + |
| biometric-applicant | термин | проверено | + | + | + | + | + | + |
| biometric-application-database | термин | проверено | + | + | + | + | + | + |
| biometric-application-decision | термин | проверено | + | + | + | + | + | + |
| biometric-attendant | термин | проверено | + | + | + | + | + | + |
| biometric-candidate-list | термин | проверено | + | + | + | + | + | + |
| biometric-candidate-score | термин | проверено | + | + | + | + | + | + |
| biometric-candidate | термин | проверено | + | + | + | + | + | + |
| biometric-capture-device | термин | проверено | + | + | + | + | + | + |
| biometric-capture-process | термин | проверено | + | + | + | + | + | + |
| biometric-capture-subject | термин | проверено | + | + | + | + | + | + |
| biometric-capture-subsystem | термин | проверено | + | + | + | + | + | + |
| biometric-capture | термин | проверено | + | + | + | + | + | + |
| biometric-characteristic | термин | проверено | + | + | + | + | + | + |
| biometric-characteristics-examiner | термин | проверено | + | + | + | + | + | + |
| biometric-claim | термин | проверено | + | + | + | + | + | + |
| biometric-data-record | термин | проверено | + | + | + | + | + | + |
| biometric-data-subject | термин | ревью нет (хэш d353e4518d4c) | + | − | − | − | + | + |
| biometric-data | термин | ревью нет (хэш d256762342af) | + | − | − | − | + | + |
| biometric-database | термин | ревью нет (хэш f34fc694f65c) | + | − | − | − | + | + |
| biometric-enrollee | термин | ревью нет (хэш c0b39b2e1c0f) | + | − | − | − | + | + |
| biometric-enrolment-data-record | термин | ревью нет (хэш a15ffdeca7bf) | + | − | − | − | + | + |
| biometric-enrolment-database | термин | ревью нет (хэш d8653725b5de) | + | − | − | − | + | + |
| biometric-enrolment | термин | ревью нет (хэш c648062fb2a6) | + | − | − | − | + | + |
| biometric-false-acceptance | термин | ревью нет (хэш f9137cf461db) | + | − | − | − | + | + |
| biometric-false-rejection | термин | ревью нет (хэш 4e3474fe20e2) | + | − | − | − | + | + |
| biometric-feature-extraction | термин | ревью нет (хэш 61f98c8c3bae) | + | − | − | − | + | + |
| biometric-feature | термин | ревью нет (хэш 3ab70c75b2cc) | + | − | − | − | + | + |
| biometric-identification-decision | термин | ревью нет (хэш e5234fe07c3c) | + | − | − | − | + | + |
| biometric-identification-system | термин | ревью нет (хэш f5a08d03fac8) | + | − | − | − | + | + |
| biometric-identification | термин | ревью нет (хэш c2d00fa0f3a7) | + | − | − | − | + | + |
| biometric-mated-comparison-trial | термин | ревью нет (хэш 94440e631dbc) | + | − | − | − | + | + |
| biometric-model | термин | ревью нет (хэш d528b56661a1) | + | − | − | − | + | + |
| biometric-non-mated-comparison-trial | термин | ревью нет (хэш 47707f43f464) | + | − | − | − | + | + |
| biometric-operational-personnel | термин | ревью нет (хэш 24ca30beb4fe) | + | − | − | − | + | + |
| biometric-presentation | термин | ревью нет (хэш cc2eeb40a537) | + | − | − | − | + | + |
| biometric-probe | термин | ревью нет (хэш 9fd8129c6011) | + | − | − | − | + | + |
| biometric-property | термин | ревью нет (хэш 58355c8c927c) | + | − | − | − | + | + |
| biometric-recognition | термин | ревью нет (хэш 3ecfd03fe69c) | + | − | − | − | + | + |
| biometric-reference-adaptation | термин | ревью нет (хэш 078011ee4832) | + | − | − | − | + | + |
| biometric-reference-data-record | термин | ревью нет (хэш d53e544cd0b0) | + | − | − | − | + | + |
| biometric-reference-database | термин | ревью нет (хэш 3266289a9894) | + | − | − | − | + | + |
| biometric-reference-identifier | термин | ревью нет (хэш 4abd4846a748) | + | − | − | − | + | + |
| biometric-reference | термин | ревью нет (хэш b38ff72b3be3) | + | − | − | − | + | + |
| biometric-representation | термин | ревью нет (хэш 864fb6c11db0) | + | − | − | − | + | + |
| biometric-sample | термин | ревью нет (хэш ba09cd8116f9) | + | − | − | − | + | + |
| biometric-search | термин | ревью нет (хэш 89addd992f9d) | + | − | − | − | + | + |
| biometric-system-operator | термин | ревью нет (хэш 8ecdee4e473d) | + | − | − | − | + | + |
| biometric-system-owner | термин | ревью нет (хэш bb4e0867bf8d) | + | − | − | − | + | + |
| biometric-system | термин | ревью нет (хэш fd65e57511ee) | + | − | − | − | + | + |
| biometric-template | термин | ревью нет (хэш 4d46f32ace22) | + | − | − | − | + | + |
| biometric-verification-decision | термин | ревью нет (хэш 974b485d3b5d) | + | − | − | − | + | + |
| biometric-verification-system | термин | ревью нет (хэш b9b4f58753cc) | + | − | − | − | + | + |
| biometric-verification | термин | ревью нет (хэш da4224de4b4d) | + | − | − | − | + | + |
| biometric | термин | ревью нет (хэш a757890b6747) | + | − | − | − | + | + |
| bona-fide-presentation | термин | ревью нет (хэш 3556b3721594) | + | − | − | − | + | + |
| capture-attempt | термин | ревью нет (хэш 0f67370d1128) | + | − | − | − | + | + |
| capture-task | термин | ревью нет (хэш 8ed14a048b0c) | + | − | − | − | + | + |
| capture-transaction | термин | ревью нет (хэш 5163f5e3dfb0) | + | − | − | − | + | + |
| captured-biometric-sample | термин | ревью нет (хэш 8c2050bc5234) | + | − | − | − | + | + |
| channel-effect | термин | ревью нет (хэш 95db7c0e4fd9) | + | − | − | − | + | + |
| claimant | термин | ревью нет (хэш 6829222132b0) | + | − | − | − | + | + |
| closed-set-test | термин | ревью нет (хэш b2aafa5d335b) | + | − | − | − | + | + |
| cognizant-presentation | термин | ревью нет (хэш c764ba6d6fc3) | + | − | − | − | + | + |
| comparison-decision | термин | ревью нет (хэш aba13c978a3a) | + | − | − | − | + | + |
| comparison-score | термин | ревью нет (хэш 0a534d0492e1) | + | − | − | − | + | + |
| comparison-trial | термин | ревью нет (хэш 54e104604ebb) | + | − | − | − | + | + |
| comparison | термин | ревью нет (хэш 24d45d183d0e) | + | − | − | − | + | + |
| computational-workload | термин | ревью нет (хэш cb1df0f7b408) | + | − | − | − | + | + |
| conformant-capture-attempt | термин | ревью нет (хэш febb27c79e44) | + | − | − | − | + | + |
| cooperative-biometric-capture-subject | термин | ревью нет (хэш 2034de0175ae) | + | − | − | − | + | + |
| cooperative-presentation | термин | ревью нет (хэш 21ecd588e228) | + | − | − | − | + | + |
| cumulative-match-characteristic-plot | термин | ревью нет (хэш 62ce79023ccc) | + | − | − | − | + | + |
| dissimilarity-score | термин | ревью нет (хэш 9049f2feb248) | + | − | − | − | + | + |
| duplicate-biometric-enrolment-check | термин | ревью нет (хэш 527cf1320e30) | + | − | − | − | + | + |
| enrol | термин | ревью нет (хэш c8b4084fda4c) | + | − | − | − | + | + |
| enrolment-attempt | термин | ревью нет (хэш fd5f29bba771) | + | − | − | − | + | + |
| enrolment-transaction | термин | ревью нет (хэш 689e2e4780bf) | + | − | − | − | + | + |
| experimenter | термин | ревью нет (хэш 490c287e9134) | + | − | − | − | + | + |
| failure-to-acquire | термин | ревью нет (хэш c040910ee068) | + | − | − | − | + | + |
| failure-to-capture | термин | ревью нет (хэш 002a7fcf054b) | + | − | − | − | + | + |
| failure-to-enrol | термин | ревью нет (хэш 89ac2e628745) | + | − | − | − | + | + |
| false-match | термин | ревью нет (хэш ca59f9a4f0d6) | + | − | − | − | + | + |
| false-non-match | термин | ревью нет (хэш b0a067521091) | + | − | − | − | + | + |
| filter | термин | ревью нет (хэш 18eddf5e89a7) | + | − | − | − | + | + |
| fraudulent-biometric-enrolment-data | термин | ревью нет (хэш 4c004dee450c) | + | − | − | − | + | + |
| full-biometric-system | термин | ревью нет (хэш 48af29c2245e) | + | − | − | − | + | + |
| identification-transaction | термин | ревью нет (хэш b00f2b181f17) | + | − | − | − | + | + |
| identify | термин | ревью нет (хэш f143b3732a57) | + | − | − | − | + | + |
| identity-concealer | термин | ревью нет (хэш bac7f904522d) | + | − | − | − | + | + |
| impostor | термин | ревью нет (хэш 3079552b63e6) | + | − | − | − | + | + |
| indifferent-biometric-capture-subject | термин | ревью нет (хэш 6c72d44e739d) | + | − | − | − | + | + |
| indifferent-presentation | термин | ревью нет (хэш 0a9230f71504) | + | − | − | − | + | + |
| intermediate-biometric-sample-processing | термин | ревью нет (хэш 8d6bf753c5cc) | + | − | − | − | + | + |
| intermediate-biometric-sample | термин | ревью нет (хэш 711d25d63197) | + | − | − | − | + | + |
| liveness-detection | термин | ревью нет (хэш 126947ef5a88) | + | − | − | − | + | + |
| liveness | термин | ревью нет (хэш c2a48cfa14bd) | + | − | − | − | + | + |


## История проверки

- 2026-10-26, задача #29: до правок — формат 63% (12 из 19), а 32% (6 из 19), б 84% (16 из 19), в 100%, г 95% (18 из 19), д 10% (2 из 19)
- 2026-10-26, задача #29: после правок — формат 100%, а 100%, б 100%, в 100%, г 100%, д 10% (2 из 19: нужен тип связи для упоминаний из источника, вопрос владельцу)
- Исправлено: выдуманные зависимости «ужесточили защиту / подстроили систему» (APCER, BPCER, FAR, FRR, FNIR, FPIR), «порог → FMR/FNMR» заменено на примечание источника (FMR, FNMR), FPIR «FMR — по парным» → «по непарным», APNRR направление «Выше» → «Ниже», IAPAR без привязки к лицу, FTE пример по транзакциям, предложения о формуле убраны из 7 текстов, TPIR ↔ FNIR «дополнение»
- 2026-10-26, решение владельца: направление «Ниже/Выше — лучше» убрано совсем — из коротких (остался только смысл, ≤ 10 слов) и длинных определений всех 19 метрик (убрано по одному предложению «Чем ниже/выше значение…»); блок г теперь проверяет отсутствие направления: 100% (19 из 19). Остальные утверждения текстов не менялись, ревью а/б/в повторено: замечаний нет
- 2026-10-26, решение владельца: связь «используется в определении» строится автоматически по тексту источника (по стандарту и в общем реестре) — блок д: 10% (2 из 19) → 100% (19 из 19)
- 2026-10-26, задача #34 (проверка Kimi K5): до правок — формат, а, б, в, г, д по 100% (19 из 19); после правок текстов ревью устарело у 6 записей (68%, 13 из 19) до повторной ручной проверки, после неё — все блоки 100% (19 из 19)
- Исправлено в #34: CAPNMR и CAPNIR — формула TN / (FP + TN) = TNR = 1 − FPR, флаг formula_na снят, фраза «для укрывателя несовпадение означает успех атаки» (п. 3.2.7, 3.2.9 ГОСТ Р 58624.3-2019); IAPIR — «идентификатора биометрического контрольного шаблона» (п. 3.2.8); BPCER короткое — «подлинное предъявление» (п. 3.2.2); FPIR короткое и длинное — «возвращается идентификатор» при незарегистрированном субъекте (п. 3.23 ГОСТ Р 71414.1-2024); APNRR короткое — «предъявление артефакта» (п. 3.2.3). Подстановка чисел: CAPNMR 6 из 100 → TN=6, FP=94, 6/(94+6)=6%; CAPNIR 5 из 100 → 5/(95+5)=5%. Остальные 13 записей проверены на «живой человек» и неточное описание возвращаемого/совпадающего — замечаний нет
