"""Hand-curated vocabulary used by the heuristic rules.

This is the main known limitation of the v0 baseline: relevance depends on
lexical overlap plus these coarse concept groups. Words here are generic
software/agent vocabulary, not phrases lifted from benchmark cases.
"""

from __future__ import annotations

# Words carrying no information about *what* an action touches.
STOPWORDS = frozenset(
    """
    a an the in on of to for and or with from by at is are was were be been being it its this that these
    those into as then than so if but not no yet please help something stuff thing things task it's do does
    did done we i me my our you your they their there here why what how where when which who whom
    any some each other same again also just only very can could should would will shall may might must
    run read get check fix make find show open use see look inspect view list search call execute perform
    try verify report current new file files tool shell command action step next now using via
    """.split()
)

# Verbs signalling that the goal requires changing something.
CHANGE_VERBS = frozenset(
    """
    fix modify edit update change set add remove delete rename refactor configure adjust replace raise
    lower increase decrease correct bump write create implement patch tweak pin
    """.split()
)

# Goal opening verbs that a single successful *execution* can complete.
EXECUTE_GOAL_VERBS = frozenset({"run", "execute", "test", "build", "install", "compile", "lint"})

# Goal opening verbs that a single successful *mutation* can complete.
WRITE_GOAL_VERBS = frozenset(
    {"fix", "edit", "update", "change", "set", "modify", "add", "remove", "delete", "rename", "replace", "correct", "bump"}
)

# Coarse topic groups. Two texts sharing a group are considered related.
CONCEPTS: dict[str, frozenset[str]] = {
    "docs": frozenset("readme docs doc documentation typo spelling wording markdown md rst changelog notes guide".split()),
    "debugging": frozenset("crash crashed error errors exception traceback stack log logs bug failure panic segfault".split()),
    "testing": frozenset("test tests pytest unittest jest spec specs coverage".split()),
    "quality": frozenset("lint linter flake8 eslint ruff pylint mypy format formatter prettier black".split()),
    "config": frozenset("config configuration settings yaml yml toml ini env dotenv".split()),
    "database": frozenset("database db sql migration migrations schema table tables query postgres mysql sqlite".split()),
    "ui": frozenset("button padding margin css style styles layout component page color font ui frontend".split()),
    "dependencies": frozenset("dependency dependencies package packages npm pip requirements lockfile yarn poetry".split()),
    "auth": frozenset("login logout auth authentication password session token signup oauth".split()),
    "network": frozenset("api endpoint http https request status service server url".split()),
    "build": frozenset("build compile ci pipeline deploy deployment release".split()),
}

# Words in the action's type/tool that identify its kind (checked in this order).
KIND_KEYWORDS: dict[str, frozenset[str]] = {
    "finish": frozenset("finish final answer respond response reply conclude".split()),
    "write": frozenset(
        """
        edit write modify update create delete remove patch apply insert append replace rename move commit
        push install uninstall upgrade deploy migrate click fill submit set save mkdir drop alter truncate
        """.split()
    ),
    "search": frozenset("search grep find lookup locate rg glob".split()),
    "request": frozenset("http api request fetch get post curl navigate browse visit goto url scrape".split()),
    "execute": frozenset("run exec execute shell bash command test pytest build compile lint make script".split()),
    "read": frozenset("read cat view open inspect list ls show describe head tail load index scan crawl select sql query".split()),
}

# Command words that make an executed command change state.
MUTATING_COMMAND_WORDS = frozenset(
    """
    install uninstall rm mv cp mkdir commit push checkout reset merge rebase apply migrate deploy restart
    start stop kill touch chmod chown sed write delete drop insert update alter truncate
    """.split()
)

# Command words that indicate a test/verification run.
TEST_COMMAND_WORDS = frozenset("test tests pytest jest unittest mocha vitest tox nox check spec".split())

DOC_EXTENSIONS = frozenset({".md", ".rst", ".txt", ".adoc"})
# Conventional documentation files that usually have no extension.
DOC_FILENAMES = frozenset({"license", "licence", "readme", "changelog", "notice", "authors", "contributors", "contributing", "copying"})

# Actions scanning far more than a narrow goal needs.
BROAD_TOOL_WORDS = frozenset({"index", "crawl", "scan"})
BROAD_PHRASES = (
    "entire",
    "whole",
    "everything",
    "all files",
    "every file",
    "all pages",
    "full repository",
    "full codebase",
    "full scan",
)

# Goals that legitimately need wide-reaching actions.
BROAD_GOAL_WORDS = frozenset(
    """
    all every entire whole across codebase repository repo global audit usage usages references
    everywhere rename refactor migrate overview survey comprehensive each
    """.split()
)
