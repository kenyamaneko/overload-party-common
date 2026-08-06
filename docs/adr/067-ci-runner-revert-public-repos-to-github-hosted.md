# ADR-067: public化済みリポの CI runner を GitHub-hosted へ戻す

## ステータス

Accepted (2026-08-06)

## 結論

public化済みリポの標準ランナーは、Ubicloud (`ubicloud-standard-2`) から GitHub-hosted の標準ランナー (`ubuntu-latest`) に戻す。[ADR-040](040-ci-runner-migration-to-ubicloud.md) の判断は private を継続するリポ (`assets`, `k8s`) にのみ適用される形で残り、Accepted のままとする。

ミューテーションテストが使う4vCPUランナー (`ubicloud-standard-4`) も、GitHub-hosted の標準ランナーに戻す。

## 背景・課題

ADR-040 は GitHub Actions の超過課金対策として、全リポの CI runner を Ubicloud に切替える判断だった。その後 overload-party の大半のリポを public化した。GitHub-hosted の標準ランナーは public リポでは無料無制限になるため、public化済みリポについては ADR-040 の前提 (超過課金の削減) が成立しなくなった。

ミューテーションテストの4vCPUランナーは、mutant ごとにテストスイートを再実行するため通常のCIより速度を優先して選んだ規格であり、実行に必須の要件ではない。GitHub-hosted の大型ランナーは Organization の Team/Enterprise Cloud プラン限定機能であり、個人アカウントでは利用できず、利用できたとしても public/private を問わず課金対象になる。

## 不採用案

- ミューテーションテストの4vCPUランナーを維持する: 試験実測した所要時間 (約3分、制限時間に対して十分な余裕がある) から、2vCPU化しても収まる見込みのため不採用
