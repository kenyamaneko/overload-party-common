using System.Xml.Linq;
using TestReport;

namespace TestReport.Tests;

[Trait("対象", "TRX outcome の解釈")]
public class OutcomeParsingTests
{
    [Theory(DisplayName = "TRX の outcome 値に対応する成否区分になる")]
    [InlineData("Passed", TestOutcome.Passed)]
    [InlineData("Failed", TestOutcome.Failed)]
    [InlineData("NotExecuted", TestOutcome.Skipped)]
    public void 既知のoutcome(string outcome, TestOutcome expected)
    {
        TrxReport.ParseOutcome(outcome).Should().Be(expected);
    }

    [Fact(DisplayName = "未知の outcome のとき、例外になる")]
    public void 未知のoutcome()
    {
        var act = () => TrxReport.ParseOutcome("Blocked");

        act.Should().Throw<InvalidOperationException>();
    }
}

[Trait("対象", "スタックトレースからのファイル位置抽出")]
public class LocationExtractionTests
{
    [Fact(DisplayName = "ワークスペース配下の絶対パスがあるとき、リポジトリルート相対のパスと行番号になる")]
    public void ワークスペース配下()
    {
        var stackTrace = "   at Namespace.Class.Method() in /repo/tests/FooTests.cs:line 42\n   at System.Reflection.MethodBaseInvoker.InterpretedInvoke_Method(Object obj, IntPtr* args)";

        var (file, line) = TrxReport.ExtractLocation(stackTrace, "/repo");

        file.Should().Be("tests/FooTests.cs");
        line.Should().Be(42);
    }

    [Fact(DisplayName = "ワークスペース外の絶対パスのとき、パスをそのまま返す")]
    public void ワークスペース外()
    {
        var stackTrace = "   at Namespace.Class.Method() in /other/FooTests.cs:line 7";

        var (file, line) = TrxReport.ExtractLocation(stackTrace, "/repo");

        file.Should().Be("/other/FooTests.cs");
        line.Should().Be(7);
    }

    [Fact(DisplayName = "スタックトレースが無いとき、位置が特定できない")]
    public void スタックトレース無し()
    {
        var (file, line) = TrxReport.ExtractLocation(null, "/repo");

        file.Should().BeNull();
        line.Should().Be(0);
    }

    [Fact(DisplayName = "ファイル位置を含む行が無いとき、位置が特定できない")]
    public void ファイル位置無し()
    {
        var stackTrace = "   at System.Reflection.MethodBaseInvoker.InterpretedInvoke_Method(Object obj, IntPtr* args)";

        var (file, line) = TrxReport.ExtractLocation(stackTrace, "/repo");

        file.Should().BeNull();
        line.Should().Be(0);
    }
}

[Trait("対象", "workflow コマンドの特殊文字エスケープ")]
public class EscapingTests
{
    [Theory(DisplayName = "メッセージ本文をエスケープする")]
    [InlineData("100%失敗", "100%25失敗")]
    [InlineData("1行目\n2行目", "1行目%0A2行目")]
    [InlineData("1行目\r2行目", "1行目%0D2行目")]
    public void データのエスケープ(string input, string expected)
    {
        TrxReport.EscapeData(input).Should().Be(expected);
    }

    [Theory(DisplayName = "プロパティ値をエスケープする")]
    [InlineData("tests/Foo:Bar.cs", "tests/Foo%3ABar.cs")]
    [InlineData("a,b.cs", "a%2Cb.cs")]
    public void プロパティのエスケープ(string input, string expected)
    {
        TrxReport.EscapeProperty(input).Should().Be(expected);
    }
}

[Trait("対象", "TRX 全体のパース")]
public class ParseTests
{
    private static XDocument BuildTrx(string resultsXml) => XDocument.Parse($"""
        <TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
          <Results>
            {resultsXml}
          </Results>
        </TestRun>
        """);

    [Fact(DisplayName = "通過したテストは Message も File も持たない")]
    public void 通過()
    {
        var trx = BuildTrx("""<UnitTestResult testName="Foo.Bar" outcome="Passed" />""");

        var results = TrxReport.Parse(trx, "/repo");

        results.Should().ContainSingle().Which.Should().Be(new TestResult("Foo.Bar", TestOutcome.Passed, null, 0, null));
    }

    [Fact(DisplayName = "失敗したテストは Message とファイル位置を持つ")]
    public void 失敗()
    {
        var trx = BuildTrx("""
            <UnitTestResult testName="Foo.Bar" outcome="Failed">
              <Output>
                <ErrorInfo>
                  <Message>Assert.Equal() Failure</Message>
                  <StackTrace>   at Foo.Bar() in /repo/tests/FooTests.cs:line 5</StackTrace>
                </ErrorInfo>
              </Output>
            </UnitTestResult>
            """);

        var results = TrxReport.Parse(trx, "/repo");

        var result = results.Should().ContainSingle().Which;
        result.Outcome.Should().Be(TestOutcome.Failed);
        result.Message.Should().Be("Assert.Equal() Failure");
        result.File.Should().Be("tests/FooTests.cs");
        result.Line.Should().Be(5);
    }

    [Fact(DisplayName = "スキップしたテストは理由を Message に持つ")]
    public void スキップ()
    {
        var trx = BuildTrx("""
            <UnitTestResult testName="Foo.Bar" outcome="NotExecuted">
              <Output>
                <ErrorInfo>
                  <Message>意図的にスキップ</Message>
                </ErrorInfo>
              </Output>
            </UnitTestResult>
            """);

        var results = TrxReport.Parse(trx, "/repo");

        var result = results.Should().ContainSingle().Which;
        result.Outcome.Should().Be(TestOutcome.Skipped);
        result.Message.Should().Be("意図的にスキップ");
    }
}
