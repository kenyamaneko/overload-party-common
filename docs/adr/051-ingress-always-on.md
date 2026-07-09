# ADR-051: 公開 Ingress を常に起動しておく

## ステータス

Accepted (2026-07-09)

## 結論

dev / stg / prod の公開 **Ingress**（外部からの入り口の設定。これを置くと GKE が Google Cloud 側に実際のロードバランサを用意する）を、常に起動したままにする。これまで環境を使うたびに作り、使い終わると消していた Ingress・DNS・固定 IP を、消さずに残す。

これで、環境の起動・停止で一番壊れやすかったロードバランサまわりの作成・削除がなくなる。Ingress は全環境とも ArgoCD が管理する形に揃い、prod だけ扱いが違っていた状態も解消する。ノードは今までどおり使わない時間帯に 0 台へ落とすので、費用削減で一番効くサーバの課金停止はそのまま残る。増える費用は、常に起動するロードバランサの月 $18 ほどだけである。

## 背景・課題

dev/stg の費用を抑えるため、ノードを 0 台に減らし、あわせてロードバランサ・DNS・固定 IP・PSC も消す運用をしてきた（ADR-018）。ノードの台数変更は `gcloud container clusters resize` 一行で済み安定しているが、ロードバランサ・DNS・固定 IP の作成と削除は手順が多く壊れやすい。ロードバランサは作成に数分かかり、削除時には使用中の IP が残らないよう順番に気をつける必要があり、DNS は環境ごとに書き換えていた。

これらを消さずに起動したままにすれば、壊れやすい手順を取り除ける。起動したままにする費用は小さく（制約に示す）、節約の主役であるノード停止は台数変更を続けるので損なわれない。

ADR-048 では、この案をロードバランサの費用が許容できないという理由で見送っていた。今回はその前提を見直す。prod が本番稼働すればこの費用はどのみち発生するし、dev/stg の分を足しても月額が小さいと公表料金で確認できたので、運用を簡単にする対価として受け入れる。

## 制約

- 課金されるのは、Ingress が用意するロードバランサ。ノードや Pod を 0 にしても消えない唯一のもので、置いてある限り課金される。料金は転送ルール 5 本までなら合計 $0.025/hr の定額なので、dev/stg/prod の 3 本で合計 月 $18 ほど。本数が 5 を超えるまでは環境が増えても変わらない。
- 固定 IP は、ロードバランサにつながって使われている間は無料。
- PSC の接続口は 1 本あたり月 $7 ほど（約 $0.01/hr）で、定額の枠がなく本数に比例する。dev/stg の 2 本で月 $15 ほどと、ロードバランサより割高。

## 詳細

常に起動しておくものと、使うときだけ立ち上げるものを分ける。

- **常に起動**: Ingress と固定 IP。Ingress は全環境とも overlay に載せ ArgoCD が管理する。dev/stg の固定 IP（`overload-party-dev-ip` / `overload-party-stg-ip`）は overload-party-infra の Terraform で確保し、prod と同じやり方で指定する。DNS はこの固定 IP を一度だけ設定して残す。
- **使うときだけ**: ノードの台数変更、Cloud SQL の起動・停止、PSC の接続口の作成・削除、夜間停止の定時実行（nightly-shutdown）。いずれも今までどおり。

環境の停止（env-lifecycle の down）は、Ingress・DNS・固定 IP の削除がなくなり、PSC の削除とノードの 0 台化だけになる。

### 変更するリポジトリ

| リポジトリ | 変更 |
|---|---|
| overload-party-k8s | dev/stg の overlay に Ingress と固定 IP を追加 / `apply-ingress.sh`・`update-dns-record.sh`・`disable-dns-record.sh`・`delete-reserved-global-ips.sh` を削除 / `env-lifecycle.yaml` から Ingress・DNS・固定 IP の手順を取り除く |
| overload-party-infra | dev/stg の固定 IP を Terraform で新設 |
| overload-party-ops | nightly-shutdown の README を、Ingress を消さない運用に合わせる |
| overload-party-common | 本 ADR |

## 不採用案

- **ノードも常に起動し、夜間は Autoscaler で減らす**: ADR-048 で見送り済み。Autoscaler でノードを 0 にするには Pod を 0 個にする必要があり、それが ArgoCD の「あるべき状態」と衝突してかえって複雑になる。ノードは台数変更で減らすやり方を続ける。
- **固定でない IP のまま DNS を設定する**: Ingress を作り直すと IP が変わり DNS が効かなくなる。固定 IP にして prod とやり方を揃える。
- **PSC も常に起動する**: 制約に示したとおりロードバランサより割高で、常時化して省けるのは PSC の作り直し手順だけ。費用に見合わない。
