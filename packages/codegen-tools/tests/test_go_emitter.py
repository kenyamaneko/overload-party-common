"""go_emitter の純粋関数群に対するユニットテスト."""

from codegen_tools.go_emitter import render_type_aliases


class Test型エイリアスの生成:
    def test_エイリアス定義をtype行に変換する(self) -> None:
        out = render_type_aliases([{"name": "ID", "base": "string"}])
        assert out == ["type ID = string", ""]

    def test_エイリアスが無ければ空リストになる(self) -> None:
        assert render_type_aliases([]) == []
