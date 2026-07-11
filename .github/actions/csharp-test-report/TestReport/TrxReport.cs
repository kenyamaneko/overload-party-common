using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace TestReport;

/// <summary>TRX 内の 1 テスト結果の成否区分。</summary>
public enum TestOutcome
{
    Passed,
    Failed,
    Skipped,
}

/// <summary>TRX から読み取った 1 テスト結果。</summary>
/// <param name="Name">テスト名 (クラス名を含む)。</param>
/// <param name="Outcome">成否区分。</param>
/// <param name="File">失敗時の発生ファイル (リポジトリルート相対)。特定できなければ null。</param>
/// <param name="Line">失敗時の発生行。File が null のとき 0。</param>
/// <param name="Message">失敗時のメッセージ。</param>
public sealed record TestResult(string Name, TestOutcome Outcome, string? File, int Line, string? Message);

public static class TrxReport
{
    private static readonly Regex StackTraceLocationRegex = new(@" in (.+\.cs):line (\d+)", RegexOptions.Compiled);

    /// <summary>TRX の outcome 属性値を <see cref="TestOutcome"/> に変換する。</summary>
    /// <param name="outcome">TRX の UnitTestResult/@outcome 値。</param>
    /// <returns>対応する成否区分。</returns>
    public static TestOutcome ParseOutcome(string outcome) => outcome switch
    {
        "Passed" => TestOutcome.Passed,
        "Failed" => TestOutcome.Failed,
        "NotExecuted" => TestOutcome.Skipped,
        _ => throw new InvalidOperationException($"unknown TRX outcome: {outcome}"),
    };

    /// <summary>TRX の XML を読み、テスト結果一覧に変換する。</summary>
    /// <param name="trx">TRX (VSTest TestRun) の XML。</param>
    /// <param name="workspace">リポジトリルートの絶対パス。スタックトレースの絶対パスをこれで相対化する。</param>
    /// <returns>テスト結果一覧。</returns>
    public static IReadOnlyList<TestResult> Parse(XDocument trx, string workspace)
    {
        var ns = trx.Root?.GetDefaultNamespace() ?? throw new InvalidOperationException("TRX root element not found");

        return trx.Descendants(ns + "UnitTestResult")
            .Select(result =>
            {
                var name = result.Attribute("testName")?.Value
                    ?? throw new InvalidOperationException("UnitTestResult/@testName not found");
                var outcome = ParseOutcome(result.Attribute("outcome")?.Value
                    ?? throw new InvalidOperationException("UnitTestResult/@outcome not found"));

                if (outcome == TestOutcome.Passed)
                {
                    return new TestResult(name, outcome, File: null, Line: 0, Message: null);
                }

                var errorInfo = result.Descendants(ns + "ErrorInfo").FirstOrDefault();
                var message = errorInfo?.Element(ns + "Message")?.Value;
                if (outcome != TestOutcome.Failed)
                {
                    return new TestResult(name, outcome, File: null, Line: 0, message);
                }

                var stackTrace = errorInfo?.Element(ns + "StackTrace")?.Value;
                var (file, line) = ExtractLocation(stackTrace, workspace);
                return new TestResult(name, outcome, file, line, message);
            })
            .ToList();
    }

    /// <summary>スタックトレースの最初のフレームから、リポジトリルート相対のファイル位置を取り出す。</summary>
    /// <param name="stackTrace">TRX の ErrorInfo/StackTrace テキスト。</param>
    /// <param name="workspace">リポジトリルートの絶対パス。</param>
    /// <returns>ファイルパス (リポジトリルート相対) と行番号。見つからなければ (null, 0)。</returns>
    public static (string? File, int Line) ExtractLocation(string? stackTrace, string workspace)
    {
        if (stackTrace is null)
        {
            return (null, 0);
        }

        var match = StackTraceLocationRegex.Match(stackTrace);
        if (!match.Success)
        {
            return (null, 0);
        }

        var absolutePath = match.Groups[1].Value;
        var line = int.Parse(match.Groups[2].Value);
        var relativePath = RelativizeToWorkspace(absolutePath, workspace);
        return (relativePath, line);
    }

    private static string RelativizeToWorkspace(string absolutePath, string workspace)
    {
        var normalizedWorkspace = workspace.TrimEnd('/') + "/";
        if (!absolutePath.StartsWith(normalizedWorkspace, StringComparison.Ordinal))
        {
            return absolutePath;
        }

        return absolutePath[normalizedWorkspace.Length..];
    }

    /// <summary>GitHub Actions workflow コマンドのデータ部 (メッセージ本文) をエスケープする。</summary>
    /// <param name="value">エスケープ対象の文字列。</param>
    /// <returns>エスケープ後の文字列。</returns>
    public static string EscapeData(string value) =>
        value.Replace("%", "%25").Replace("\r", "%0D").Replace("\n", "%0A");

    /// <summary>GitHub Actions workflow コマンドのプロパティ値 (file 等) をエスケープする。</summary>
    /// <param name="value">エスケープ対象の文字列。</param>
    /// <returns>エスケープ後の文字列。</returns>
    public static string EscapeProperty(string value) =>
        EscapeData(value).Replace(":", "%3A").Replace(",", "%2C");
}
