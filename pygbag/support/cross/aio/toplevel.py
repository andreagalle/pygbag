import sys
import aio

# https://bugs.python.org/issue34616
# https://github.com/ipython/ipython/blob/320d21bf56804541b27deb488871e488eb96929f/IPython/core/interactiveshell.py#L121-L150

import asyncio
import ast
import code
import types
import inspect
import zipfile


def install(pkg_file, sconf=None):
    from installer import install
    from installer.destinations import SchemeDictionaryDestination
    from installer.sources import WheelFile

    # Handler for installation directories and writing into them.
    destination = SchemeDictionaryDestination(
        sconf or __import_("sysconfig").get_paths(),
        interpreter=sys.executable,
        script_kind="posix",
    )

    try:
        with WheelFile.open(pkg_file) as source:
            install(
                source=source,
                destination=destination,
                # Additional metadata that is generated by the installation tool.
                additional_metadata={
                    "INSTALLER": b"pygbag",
                },
            )
    except Exception as ex:
        pdb(f"82: cannot install {pkg_file}")
        sys.print_exception(ex)


async def get_repo_pkg(pkg_file, pkg, resume, ex):
    # print("-"*40)
    import platform
    import json
    import sysconfig
    import importlib
    from pathlib import Path

    sconf = sysconfig.get_paths()
    # sconf["platlib"] = os.environ.get("HOME","/tmp")
    platlib = sconf["platlib"]
    Path(platlib).mkdir(exist_ok=True)
    # print(f"{platlib=}")

    if platlib not in sys.path:
        sys.path.append(platlib)
    try:
        aio.toplevel.install(pkg_file, sconf)
    except Exception as rx:
        pdb(f"failed to install {pkg_file}")
        sys.print_exception(rx)

    await asyncio.sleep(0)

    try:
        platform.explore(platlib)
        await asyncio.sleep(0)
        importlib.invalidate_caches()
        # print(f"{pkg_file} installed, preloading", embed.preloading())
    except Exception as rx:
        pdb(f"failed to preload {pkg_file}")
        sys.print_exception(rx)

    if resume and ex:
        try:
            if inspect.isawaitable(resume):
                print(f"{resume=} is an awaitable")
                return resume()
            else:
                print(f"{resume=} is not awaitable")
                resume()
                return asyncio.sleep(0)
        except Exception as resume_ex:
            sys.print_exception(ex, limit=-1)
    #        finally:
    #            print("-"*40)
    return None


class AsyncInteractiveConsole(code.InteractiveConsole):
    instance = None
    console = None

    def __init__(self, locals, **kw):
        super().__init__(locals)
        self.compile.compiler.flags |= ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        self.line = ""
        self.buffer = []
        self.one_liner = True
        self.opts = kw
        self.coro = None
        self.rv = None

    # need to subclass
    # @staticmethod
    # def get_pkg(want, ex=None, resume=None):

    def process_shell(self, shell, line, **env):
        catch = True
        for cmd in line.strip().split(";"):
            cmd = cmd.strip()
            if cmd.find(" ") > 0:
                cmd, args = cmd.split(" ", 1)
                args = args.split(" ")
            else:
                args = ()

            if hasattr(shell, cmd):
                fn = getattr(shell, cmd)

                try:
                    if inspect.isgeneratorfunction(fn):
                        for _ in fn(*args):
                            print(_)
                    elif inspect.iscoroutinefunction(fn):
                        aio.create_task(fn(*args))
                    elif inspect.isasyncgenfunction(fn):
                        print("asyncgen N/I")
                    elif inspect.isawaitable(fn):
                        print("awaitable N/I")
                    else:
                        fn(*args)

                except Exception as cmderror:
                    print(cmderror, file=sys.stderr)
            elif cmd.endswith('.py'):
                self.coro = shell.source(cmd, *args, **env)
            else:
                catch = undefined
        return catch

    def runsource(self, source, filename="<stdin>", symbol="single"):
        if len(self.buffer)>1:
            symbol = "exec"

        try:
            code = self.compile(source, filename, symbol)
        except SyntaxError:
            if self.one_liner:
                shell = self.opts.get("shell", None)
                if shell and self.process_shell(shell, self.line):
                    return
            self.showsyntaxerror(filename)
            return False

        except (OverflowError, ValueError):
            # Case 1
            self.showsyntaxerror(filename)
            return False

        if code is None:
            # Case 2
            return True

        # Case 3
        self.runcode(code)
        return False

    def runcode(self, code):
        embed.set_ps1()
        self.rv = undefined

        bc = types.FunctionType(code, self.locals)
        try:
            self.rv = bc()
        except SystemExit:
            raise

        except KeyboardInterrupt as ex:
            print(ex, file=sys.__stderr__)
            raise

        except ModuleNotFoundError as ex:
            get_pkg = self.opts.get("get_pkg", self.get_pkg)
            if get_pkg:
                want = str(ex).split("'")[1]
                self.coro = get_pkg(want, ex, bc)

        except BaseException as ex:
            if self.one_liner:
                shell = self.opts.get("shell", None)
                if shell:
                    # coro maybe be filler by shell exec
                    if self.process_shell(shell, self.line):
                        return
            sys.print_exception(ex, limit=-1)

        finally:
            self.one_liner = True

    async def interact(self):
        try:
            sys.ps1
        except AttributeError:
            sys.ps1 = ">>> "

        try:
            sys.ps2
        except AttributeError:
            sys.ps2 = "--- "

        cprt = 'Type "help", "copyright", "credits" or "license" for more information.'

        self.write(
            "Python %s on %s\n%s\n(%s)\n"
            % (sys.version, sys.platform, cprt, self.__class__.__name__)
        )

        prompt = sys.ps1

        while not aio.exit:
            await asyncio.sleep(0)
            self.coro = None
            try:
                try:
                    self.line = self.raw_input(prompt)
                    if self.line is None:
                        continue
                except EOFError:
                    self.write("\n")
                    break
                else:
                    if self.push(self.line):
                        prompt = sys.ps2
                        embed.set_ps2()
                        self.one_liner = False
                    else:
                        prompt = sys.ps1

            except KeyboardInterrupt:
                self.write("\nKeyboardInterrupt\n")
                self.resetbuffer()
                more = 0
            try:
                # if async prepare is required
                if self.coro is not None:
                    self.rv = await self.coro

                if self.rv not in [undefined, None, False, True]:
                    await self.rv
            except Exception as ex:
                sys.print_exception(ex)

            embed.prompt()

        self.write("now exiting %s...\n" % self.__class__.__name__)

    @classmethod
    def start_console(cls, shell):
        """will only start a console, not async import system"""
        if cls.instance is None:
            cls.instance = cls(
                globals(),
                shell=shell,
            )
            PyConfig.aio = cls.instance

        if cls.console is None:
            asyncio.create_task(cls.instance.interact())
            cls.console = cls.instance


    @classmethod
    async def start_toplevel(cls, shell, console=True):
        """start async import system with optionnal async console"""
        cls.instance = cls(
            globals(),
            shell=shell,
        )

        await cls.instance.async_repos()

        if console:
            cls.start_console(shell)




