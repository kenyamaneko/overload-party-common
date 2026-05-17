# ADR-044: reactive 効果の解決モデル再設計 — トリガーの event 化とチェーン機構の不採用

## ステータス

Proposed (2026-05-17)

## コンテキスト

battle の reactive 効果の解決モデルに複数の未完成・不整合があり、[battle#56](https://github.com/kenyamaneko/overload-party-battle/issues/56) で表面化した。本 ADR はその解決モデルを定める。

判明している問題:

- **`reactive` トリガーが過負荷**。`reactive` は「いつ発火するか」を表す event ではなく、リアクティブというカード種別から借りたトリガー名になっている。`trigger: reactive` を持つカードは 15 枚あり、攻撃宣言時 / リソースのデプロイ時 / リソースの破壊時 / インシデント使用時 / 被ダメージ時 という異なる event を 1 つのトリガー名に押し込んでいる。さらに `reactive` は `Reactive` カード種別だけでなく Platform / Attachment / Compute にも付いている。
- **発火点が攻撃宣言時の 1 つだけ**。`reactive` トリガーを消費するのは `AttackProcessor.FireReactives` のみで、攻撃宣言時・ダメージ前に DeployOrder 最小の 1 枚を無条件発火する。このため「破壊された時」系カード（NT-0023 / TK-0024 / TN-0018）は破壊が起きていなくても毎攻撃発火し、インシデント反応カードは発火経路が無く、サポートゾーンに居ない TK-0002（Compute）は走査対象外で永久に発火しない。
- **チェーン機構がデッドコード**。RULEBOOK §12 は遊戯王準拠のチェーン（LIFO・最大 3）を規定し、`ChainResolver` / `BattleGameState.ChainStack` / `ChainEntry` が実装済みだが、ゲームロジックからの呼び出しはゼロ。DB の `chain_stack` カラムには空配列が往復するだけ。

[battle#54](https://github.com/kenyamaneko/overload-party-battle/issues/54)（reactive のプレイヤー選択ギャップ）は本解決モデルの上に乗るため、本 ADR が前提となる。

## 決定

### 設計の骨子

1. **`reactive` トリガーを廃止し、event 単位のトリガーに統合する。** reactive が応じる event を `on_attack_declared`（攻撃宣言時・ダメージ前）/ `on_deploy`（リソースのデプロイ時）/ `on_destroy`（リソースの破壊時）/ `on_incident`（インシデント使用時）/ `on_damaged`（リソースの被ダメージ時）に分解する。
2. **`deploy` と `on_enemy_deploy` を `on_deploy` に統合する。** トリガーは「リソースがデプロイされた」という event のみを表す。自分のデプロイか相手のデプロイか、デプロイされたカード自身の効果（ETB）か別カードの監視効果かは、guard 述語と card_type で判定する。
3. **トリガーは event だけを表し、発火条件は guard で表現する。** 「攻撃者が天気使い」「致死攻撃」「可用性しきい値」などの条件はトリガー種別に畳まず、guard 述語として表現する。
4. **1 つの event につき発動するリアクティブ（card_type == `Reactive`）は、最も早くセットされた 1 枚のみ。** 発動時に表向き化してトラッシュへ送る使い切り挙動も card_type == `Reactive` で判定する。
5. **RULEBOOK §12 のチェーンスタックは採用しない。** `ChainResolver` / `BattleGameState.ChainStack` / `ChainEntry` および DB の `chain_stack` カラムを削除する。

### トリガー再編と発火モデル

| 操作 | トリガー |
|---|---|
| 廃止 | `reactive` |
| 統合 | `deploy` ＋ `on_enemy_deploy` → `on_deploy` |
| リネーム | `activate` → `ignition` |
| 新設 | `on_attack_declared` / `on_incident` / `on_damaged` |
| 据置 | `passive` / `on_end_phase` / `on_field_change` / `on_scale_up` / `on_attack` / `on_hit` / `on_destroy` |

`on_deploy` の発火 event は「リソースが表向き・稼働状態でフィールドに入った瞬間」とする。デプロイターンのカウントダウン完了、および deploy_turns=0 の即時デプロイがこれに当たる。サポートゾーンへの裏向きセットおよびカウントダウン中の裏向き状態は `on_deploy` event ではない。

`activate` は `ignition` に改名する。これはプレイヤーが手動で発動する起動効果のトリガーであり、イベントに自動反応する `on_*` 群とは別カテゴリであることを名前で示す（遊戯王の Ignition Effect に倣う）。

各トリガーの発火モデルは次のとおり:

- **発火点**: 各トリガーは対応する event の処理箇所で発火する。`on_attack_declared` は攻撃宣言時・ダメージ前、`on_deploy` はデプロイ処理、`on_destroy` は破壊処理、`on_incident` はインシデント使用処理、`on_damaged` はリソースへのダメージ適用時。
- **走査範囲**: 発火点は、そのトリガーを持つカードが存在しうる場所をすべて走査する。`on_destroy` はフィールド上リソースに加えサポートゾーンの伏せカードを走査する。`on_incident` はサポートゾーンとフィールド上リソースの両方を走査する（Compute リソースである TK-0002 を取りこぼさないため）。
- **1 枚制限**: 1 つの event に対し、条件を満たす card_type == `Reactive` のカードのうち最も早くセットされた 1 枚のみが発動する。これは攻撃宣言・デプロイ・破壊・インシデント・被ダメージのすべての event に一律に適用する。
- **使い切り**: card_type == `Reactive` のカードは発動時に表向き化し、効果解決後にトラッシュへ送る。Platform / Attachment / Compute は使い切りではなく残存し、event ごとに繰り返し発火しうる（持続的な監視効果）。
- **`on_deploy` の 2 段解決**: デプロイをキャンセルする監視効果（NT-0034）は、デプロイされたカード自身の ETB 効果より前に解決する。攻撃の「リアクティブ → ダメージ」と同じ逐次パターンである。

### なぜこの設計か

| 観点 | 評価 |
|---|---|
| トリガー体系の一貫性 | event 単位トリガーは既存の `on_attack` / `on_hit` / `on_destroy` / `on_field_change` と同じ確立パターン。`reactive` だけがカード種別由来でこの体系から外れていた |
| 条件表現の分離 | 「いつ（event）」をトリガーに、「条件」を guard 述語に分離する。`on_*` トリガーを条件付きで細分化（`reactive_on_lethal_attack` 等）すると event 軸の分類が二重化するため採らない |
| `on_deploy` 統合 | 「リソースがデプロイされた」は単一 event。ETB（自分のデプロイに自分が反応）と監視効果（他者のデプロイに反応）の差は card_type と guard で吸収でき、トリガーを分ける必然がない。「enemy」という語も `on_enemy_deploy` 以外で使われておらず、フリート共通の「opponent」表記に揃わない |
| チェーン不採用 | リアクティブにリアクティブを積めず、カウンター罠相当のカードが存在せず、リアクティブは全自動発動でプレイヤーが動的にチェーンを構築しない。この前提下ではスタックという構造は観測可能な挙動差を生まない。「リアクティブを先に解決してから行動を処理する」順序は processor 内の逐次コードで表現でき（現に `FireReactives` はダメージ適用前に解決している）、スタックは不要 |

### 検討した代替案

#### 案: RULEBOOK §12 のチェーンスタックを実装する

却下理由: reactive-on-reactive 禁止・カウンター罠なし・全自動発動という前提下では、スタックは観測可能な挙動差を生まない。「キャンセル → ダメージ → 破壊」は処理順が一意に決まっており LIFO で表現できず、結局スタック内で処理順を別管理する二重化になる。

#### 案: `reactive` トリガーを `reactive_on_attack` / `reactive_on_destroy` 等に細分化する

却下理由: event 軸のトリガー分類を `on_*` ファミリと二重に持つことになる。リアクティブはカード種別（サポートゾーンに伏せる使い切りカード）であってトリガー軸ではない。

#### 案: `deploy` と `on_enemy_deploy` を別トリガーのまま残す

却下理由: 「リソースがデプロイされた」は単一 event。発火する側が ETB か監視効果かはトリガー名ではなく card_type と guard で表現でき、トリガーを 2 つに割る必然がない。

### battle#54 / battle#22 との関係

- **battle#54**（reactive のプレイヤー選択）は本モデルの上に乗る。reactive 効果の解決中にプレイヤー選択を挟む仕組み（アクションの中断・再開）は本 ADR のスコープ外とし、battle#54 で設計する。これは RULEBOOK §12 のチェーンとは別概念であり、チェーン不採用は battle#54 を妨げない。
- **battle#22**（効果ガードの述語化）は本 ADR と独立。本 ADR で追加する guard は現行の guard 機構で表現し、battle#22 が後で全 guard を一律に述語化する。依存順は battle#56（本 ADR）→ battle#54 → battle#22 の一直線であり、循環しない。

## 実装方針

### トリガー定義とローダ

- `data/game_logic_constants.yaml`（battle リポ）の `trigger_types` を再編し、`generate_constants.py` を再実行する。
- `TriggerType` enum と `EffectYamlLoader.ParseTrigger` を新トリガー集合に揃える。unknown トリガー → throw の方針は維持する。

### 発火点

- `AttackProcessor`: 攻撃宣言時・ダメージ前の reactive 発火を `on_attack_declared` として扱う。
- `PlayCardProcessor`: ETB（旧 `deploy`）と デプロイ監視（旧 `on_enemy_deploy`）の発火点を `on_deploy` の単一発火点に統合する。インシデント使用処理に `on_incident` 発火点を新設する。
- `FireOnDestroy`: 走査範囲をサポートゾーンの伏せカードまで拡張する。
- `on_damaged`: リソースへのダメージ適用箇所（攻撃・インシデント・効果 op）に発火点を設ける。ダメージ適用の単一チョークポイントを設けるか、各適用箇所にフックを置く。

### カード再割当

`trigger: reactive` を持つ 15 枚と `on_enemy_deploy` の 2 枚を新トリガーへ付け替える。effect_text の条件は guard 述語で表現する（effect_text をカード仕様の SSoT とする）。

| 新トリガー | カード（card_type） |
|---|---|
| `on_attack_declared` | NT-0024 / NT-0028（Reactive）、NT-0027（Reactive・攻撃者 faction guard を新規追加）、SL-0024（Reactive・致死 guard を新規追加） |
| `on_destroy` | NT-0023 / TK-0024 / TN-0018（Reactive・破壊対象の faction / type guard を新規追加） |
| `on_incident` | TK-0023（Reactive）、SH-0014 / TK-0014 / TN-0013（Platform）、SH-0017 / TK-0017（Attachment）、TK-0002（Compute）。各カードに対象インシデントの guard |
| `on_damaged` | SH-0021（Reactive・SHE faction ＆ 可用性しきい値 guard） |
| `on_deploy` | NT-0022 / NT-0034（相手デプロイの guard）、および既存 `deploy` トリガーを持つ全カードの trigger 値リネーム |

カードデータの付随修正:

- リアクティブの effect_text の「発動できる」は「発動する」に書き換える（リアクティブは全自動発動でプレイヤー宣言を伴わないため）。
- SH-0021 は effect_text が回復のみを記述しているため、ops の `cancel_action` を削除する（effect_text を SSoT とする）。
- `trigger: activate` を持つ全カードの trigger 値を `ignition` にリネームする（機械的変更）。

### チェーン機構の削除

`ChainResolver` / `BattleGameState.ChainStack` / `ChainEntry` / `ChainResolverTests` を削除し、DB スキーマから `chain_stack` カラムを削除するマイグレーションを行う。

## 結果

### Positive

- トリガー体系が event 軸に統一され、`reactive` という借り物トリガーが解消される。
- 「破壊された時」「インシデント使用時」系カードが意図どおりのタイミングで発火する。サポートゾーンに居ない TK-0002 も発火経路を得る。
- 「いつ」と「条件」が trigger / guard に分離され、新カードはトリガー＋guard の組で表現できる。
- デッドコードとなっていたチェーン機構と DB カラムが削除される。

### Negative

- `reactive` および `on_enemy_deploy` を持つカードに加え、既存 `deploy` トリガーの全カードで trigger 値の書き換えが発生する。
- `on_damaged` のためにダメージ適用箇所へフックを入れる必要がある。
- DB スキーマ変更（`chain_stack` カラム削除）を伴う。

### 緩和策

- カードデータの trigger 書き換えは機械的変更であり、`generate_constants.py` の unknown → throw により取りこぼしは検知される。
- DB マイグレーションは `chain_stack` が未使用カラムであるため、データ移行を伴わない単純な列削除で済む。

## 連動する変更

| リポ | 変更 |
|---|---|
| common | 本 ADR-044 起草、RULEBOOK §5（リアクティブの発火タイミングと 1 枚制限）・§12（チェーン記述の差し替え）の amendment、`docs/notes/EFFECT_YAML_SCHEMA.md` のトリガー表更新 |
| battle | `data/game_logic_constants.yaml` の `trigger_types` 再編＋再生成、`TriggerType` / `EffectYamlLoader`、発火点（`AttackProcessor` / `PlayCardProcessor` / `FireOnDestroy` / `on_damaged`）、カードデータの trigger 付け替え＋guard 追加＋effect_text 修正、チェーン機構削除＋DB マイグレーション |

EFFECT_YAML_SCHEMA.md のトリガー表更新は battle の実装と挙動が一致する時点で行う。

## 関連

- battle issue [#56](https://github.com/kenyamaneko/overload-party-battle/issues/56): 本 ADR の起点
- battle issue [#54](https://github.com/kenyamaneko/overload-party-battle/issues/54): 本モデルの上に乗る。reactive のプレイヤー選択ギャップ
- battle issue [#22](https://github.com/kenyamaneko/overload-party-battle/issues/22): 効果ガードの述語化。本 ADR と独立
