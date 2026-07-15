# ADR-024: サービス間結合テスト戦略とテストダブルのパッケージ同梱

## ステータス

Accepted (2026-04-22)

## 結論

サービス間結合検証の空白を埋めるため、テストピラミッドの語彙定義・**送信側パッケージへのテストダブル同梱**・**nightly cloud integration** の 3 点を採用する。[ADR-015](015-package-split.md) の「送信側所有」原則がテストダブル層にも一貫して適用され、契約変更時の consumer 側追従が import 更新だけで済む。テストの所有権が各サービス repo に閉じて「落ちたテストを誰が直すか」が自明になり、「アダプターテスト」と「サービス間結合テスト」の語彙分離により「このテストは何を証明しているか」が会話の前提として揃う。emulator / 本番の乖離は nightly cloud integration で継続的に検知され、build tag / CI ジョブ分離により unit ジョブが Docker 非依存になる。

## 背景・課題

[ADR-016](016-repository-testing-testcontainers.md) でリポジトリ層（DB 境界）のテスト戦略は決まったが、**サービス間** の結合テストをどこでどう書くかは未定義のまま各サービスが独自に進めている。現時点で次のばらつきが発生している：

- `overload-party-shop`: Pub/Sub emulator + Testcontainers + `//go:build integration` タグの運用が成熟しつつある
- `overload-party-account` / `overload-party-news` / `overload-party-scenario`: `integration` build tag 運用あり、CI でジョブ分離している
- `overload-party-card` / `overload-party-gateway` / `overload-party-matchmaking` / `overload-party-support`: 統合テストと単体テストが同一ジョブ・同一タグ空間に混在している
- `overload-party-battle` (C#): 言語差のため Go 側と別建ての整備が必要
- テストダブル（mock / fake）は各サービスが手書きしており、送信側サービスが型定義を所有する [ADR-015](015-package-split.md) の原則に沿った「fake も送信側が配布」という状態になっていない

また [ADR-016](016-repository-testing-testcontainers.md) は **Cloud SQL と同じ DB エンジンで検証する** ことを決めたが、「本物の Cloud SQL / 本物の Firestore / 本物の Cloud Pub/Sub」に対する検証は CI 経路に存在しない。emulator / Testcontainers と本番の乖離（Firestore インデックス要求、Cloud SQL 接続プール設定、Pub/Sub Exactly-Once 配信の挙動等）は手動動作確認に依存している。

さらに `overload-party-e2e` は空で実装されておらず、サービス横断のテストは事実上 E2E 層にも統合テスト層にも存在しない。**サービス間結合検証の空白を埋める設計判断** が必要である。

## 不採用案

### サービス間結合テスト専用のリポジトリを新設

却下。所有権が消える（テストが落ちたときどちらのサービスチームが直すかが自明でない）、追従コストが爆発する（送信側サービスの契約変更が別リポの PR として追いかける運用になる）、ローカル開発で全サービス起動が必須になり日常的に回らなくなる。`overload-party-e2e` が担うユーザー視点の E2E とも責務が重複する。

### 各サービスが相手サービスの fake を独自に手書きし続ける

却下。[ADR-015](015-package-split.md) で「送信側が契約を所有」と決めた原則に反する。契約変更のたびに consumer 側の手書き fake が古い契約を前提に動き続ける乖離が起きる（既に shop repo 内で `fakeShopServicer` 等が ad hoc に定義されている）。スケールしない。

### Contract Testing (Pact 等) の全面導入

見送り。consumer-driven contract test は乖離検知の正攻法だが、Go / C# / Python の 3 言語 × 7 サービスで導入・運用するには先行投資が大きい。**乖離検知の第一手段は nightly cloud integration test（本 ADR で採用）に任せ**、Pact は fake と実装の不整合が実害として顕在化したタイミングで再検討する。
