from infra.util import Namespace
import infra
import os


def add_env_var(ctx: Namespace, var: str, val: str) -> None:
    """
    Adds a variable to the ``ctx.runenv``. If the variable does not exists 
    in ``ctx`` it is initialized with the contents of the corresponding 
    system enviromental variable.

    :param ctx: the configuration context
    :param var: the variable to set
    :param val: the value of the variable
    """
    if var not in ctx.runenv:
        ctx.runenv[var] = [path for path in os.getenv(
            var, '').split(':') if path]
    ctx.runenv[var] += [val]


def git_fetch(ctx: Namespace, url: str, sha: str = None,
              destination: str = 'src') -> None:
    """
    Downloads the contents of a git repository and optionally checkouts
    to a specific commit.

    :param url: the url of the git repository
    :param sha: the sha of the commit to checkout to (optional)
    :param destination: the destination folder to clone the git repository
    """
    infra.util.require_program(ctx, 'git')
    infra.util.run(ctx, 'git clone %s %s' % (url, destination))
    if sha:
        current_dir = os.getcwd()
        os.chdir(destination)
        infra.util.run(ctx, 'git checkout ' + sha)
        os.chdir(current_dir)
