
## PowerShell Bot

This is the repository for [u/PowerShell-Bot].

[u/PowerShell-Bot]: https://www.reddit.com/u/PowerShell-Bot

The goal of the bot is to teach Redditors on the [r/PowerShell] subreddit how to
properly format their code in their submission text by using code blocks. When the
submission author fixes their submission the bot notices and modifies its comment
reply accordingly.

[r/PowerShell]: https://www.reddit.com/r/PowerShell

Thanks to [u/Ta11ow] \([vexx32]\) for the idea of saving [u/Lee_Dailey] some copy-pasting,
and putting together the [original regex to detect PowerShell code snippets][subm_8jz1rn].

[u/Ta11ow]: https://www.reddit.com/u/Ta11ow
[vexx32]: https://github.com/vexx32
[u/Lee_Dailey]: https://www.reddit.com/u/Lee_Dailey
[subm_8jz1rn]: https://www.reddit.com/r/PowerShell/comments/8jz1rn/meta_regex_to_detect_common_ps_code_snippets/

The bot was originally created by me in 2019 and ran for the majority of that year. The
bot performed well and received excellent feedback but I decided to switch it off when
summer arrived because the Raspberry Pi became too hot. Ultimately though I was
unsatisfied with the quality of the codebase: the bot’s logic was difficult to follow and
it didn’t set a good example of how to write a good Reddit bot. I also found PRAW, the
Python Reddit API Wrapper package, to be annoying to work with, so I created RedditWarp,
a new Reddit API library. I’ve completely rewritten the bot in 2022 using this new
library, and the codebase is now much more comprehensible.

This is the first ever bot built using the [RedditWarp][RedditWarp PyPI] library.
This codebase is a good demonstration of how to use the library to create a bot.
The codebase features a variety of techniques and tools, such as asynchronous
programming, signal handling, logging, messaging queues, loading from configuration
files, SQL (via SQLAlchemy), and a command line interface to start the bot or invoke
various related functions.

[RedditWarp PyPI]: https://pypi.org/project/redditwarp/

### Instructions

The program requires Python 3.8+.

Configuration files from the current directory are required by the bot.
The program will also read and write to files in the current directory.
It is recommended that you create a dedicated project directory which includes
a symbolic link named `powershell_bot` to the package source.

To view the bot program’s available command line parameters:

```shell
python -m powershell_bot --help
```

Use the `run` sub-command to start the actual bot.

### Configuration files

Configuration files are searched for in the current directory. These files are not
shown in the repo and they should be created prior to running the bot.

* `powershell_bot.ini`

    Keys:

    * `database_url`: The database URL for SQLAlchemy to connect to.

    * `reddit_user_name`: The name of the Reddit account this bot will run on. Case sensitive.
        The name is used as the section name to access credentials for in the `praw.ini` file.
        It must be an exact match to the section name in the `praw.ini` file and to the
        account name this bot will run on on Reddit.

    * `target_subreddit_name`: The subreddit name in which this bot will run on. Case insensitive.

    * `advanced_comment_replying_enabled`: Whether advanced comment replying is enabled.

        Value is a boolean: see the Python `configparser` module [documentation][ConfigParser_getboolean]
        for acceptable boolean string values.

        [ConfigParser_getboolean]: https://docs.python.org/3/library/configparser.html#configparser.ConfigParser.getboolean

        Normally, if the bot gets a comment that says “Good bot” then the bot will reply with
        “Good human”, but if the comment is something else then, if this option is enabled,
        advanced comment replying will happen. The code for this logic is not supplied in this
        repository, so if you intend to run this codebase yourself then you’ll need to implement
        this feature on your own if you want it. This can be done by writing a function named
        `get_advanced_comment_reply` in a module named `powershell_bot_snapins.advanced_comment_replying`.
        See the codebase for hints.

* `praw.ini`

    Must contain a section name that matches the value of the `reddit_user_name` configuration
    in the  `powershell_bot.ini` file. The credentials in this section are used to instantiate
    the RedditWarp client.
