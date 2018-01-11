"""
Auto-generate methods for PARI functions.
"""

#*****************************************************************************
#       Copyright (C) 2015 Jeroen Demeyer <jdemeyer@cage.ugent.be>
#                     2017 Vincent Delecroix <vincent.delecroix@labri.fr>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#                  http://www.gnu.org/licenses/
#*****************************************************************************

from __future__ import absolute_import, print_function, unicode_literals
import os, re, sys, io

from .args import PariArgumentGEN, PariInstanceArgument
from .parser import read_pari_desc, parse_prototype
from .doc import get_rest_doc


gen_banner = '''# This file is auto-generated by {}

cdef class Gen_auto:
    """
    Part of the :class:`Gen` class containing auto-generated functions.

    This class is not meant to be used directly, use the derived class
    :class:`Gen` instead.
    """
'''.format(os.path.relpath(__file__, os.getcwd()))

instance_banner = '''# This file is auto-generated by {}

cdef class Pari_auto:
    """
    Part of the :class:`Pari` class containing auto-generated functions.

    You must never use this class directly (in fact, Python may crash
    if you do), use the derived class :class:`Pari` instead.
    """
'''.format(os.path.relpath(__file__, os.getcwd()))

decl_banner='''# This file is auto-generated by {}

from .types cimport *

cdef extern from *:
'''.format(__file__)


function_re = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
function_blacklist = {"O",  # O(p^e) needs special parser support
        "alias",            # Not needed and difficult documentation
        "listcreate",       # "redundant and obsolete" according to PARI
        "allocatemem",      # Better hand-written support in Pari class
        "global",           # Invalid in Python (and obsolete)
        "inline",           # Total confusion
        "uninline",         # idem
        "local",            # idem
        "my",               # idem
        }


class PariFunctionGenerator(object):
    """
    Class to auto-generate ``auto_gen.pxi`` and ``auto_instance.pxi``.

    The PARI file ``pari.desc`` is read and all suitable PARI functions
    are written as methods of either :class:`Gen` or
    :class:`Pari`.
    """
    def __init__(self):
        self.gen_filename = os.path.join('cypari2', 'auto_gen.pxi')
        self.instance_filename = os.path.join('cypari2', 'auto_instance.pxi')
        self.decl_filename = os.path.join('cypari2', 'auto_paridecl.pxd')

    def can_handle_function(self, function, cname="", **kwds):
        """
        Can we actually handle this function?

        EXAMPLES::

            >>> from autogen.generator import PariFunctionGenerator
            >>> G = PariFunctionGenerator()
            >>> G.can_handle_function("bnfinit", "bnfinit0", **{"class":"basic"})
            True
            >>> G.can_handle_function("_bnfinit", "bnfinit0", **{"class":"basic"})
            False
            >>> G.can_handle_function("bnfinit", "bnfinit0", **{"class":"hard"})
            False
        """
        if function in function_blacklist:
            # Blacklist specific troublesome functions
            return False
        if not function_re.match(function):
            # Not a legal function name, like "!_"
            return False
        cls = kwds.get("class", "unknown")
        sec = kwds.get("section", "unknown")
        if cls != "basic":
            # Different class: probably something technical or
            # specific to gp or gp2c
            return False
        if sec == "programming/control":
            # Skip if, return, break, ...
            return False
        return True

    def handle_pari_function(self, function, cname, prototype="", help="", obsolete=None, **kwds):
        r"""
        Handle one PARI function: decide whether or not to add the
        function, in which file (as method of :class:`Gen` or
        of :class:`Pari`?) and call :meth:`write_method` to
        actually write the code.

        EXAMPLES::

            >>> from autogen.parser import read_pari_desc
            >>> from autogen.generator import PariFunctionGenerator
            >>> G = PariFunctionGenerator()
            >>> G.gen_file = sys.stdout
            >>> G.instance_file = sys.stdout
            >>> G.decl_file = sys.stdout
            >>> G.handle_pari_function("bnfinit",
            ...     cname="bnfinit0", prototype="GD0,L,DGp",
            ...     help=r"bnfinit(P,{flag=0},{tech=[]}): compute...",
            ...     **{"class":"basic", "section":"number_fields"})
                GEN bnfinit0(GEN, long, GEN, long)
                def bnfinit(P, long flag=0, tech=None, long precision=0):
                    ...
                    cdef GEN _P = P.g
                    cdef GEN _tech = NULL
                    if tech is not None:
                        tech = objtogen(tech)
                        _tech = (<Gen>tech).g
                    precision = prec_bits_to_words(precision)
                    sig_on()
                    cdef GEN _ret = bnfinit0(_P, flag, _tech, precision)
                    return new_gen(_ret)
            <BLANKLINE>
                ...
            >>> G.handle_pari_function("ellmodulareqn",
            ...     cname="ellmodulareqn", prototype="LDnDn",
            ...     help=r"ellmodulareqn(N,{x},{y}): return...",
            ...     **{"class":"basic", "section":"elliptic_curves"})
                GEN ellmodulareqn(long, long, long)
                def ellmodulareqn(self, long N, x=None, y=None):
                    ...
                    cdef long _x = -1
                    if x is not None:
                        _x = get_var(x)
                    cdef long _y = -1
                    if y is not None:
                        _y = get_var(y)
                    sig_on()
                    cdef GEN _ret = ellmodulareqn(N, _x, _y)
                    return new_gen(_ret)
            <BLANKLINE>
            >>> G.handle_pari_function("setrand",
            ...     cname="setrand", prototype="vG",
            ...     help=r"setrand(n): reset the seed...",
            ...     doc=r"reseeds the random number generator...",
            ...     **{"class":"basic", "section":"programming/specific"})
                void setrand(GEN)
                def setrand(n):
                    r'''
                    Reseeds the random number generator...
                    '''
                    cdef GEN _n = n.g
                    sig_on()
                    setrand(_n)
                    clear_stack()
            <BLANKLINE>
                def setrand(self, n):
                    r'''
                    Reseeds the random number generator...
                    '''
                    n = objtogen(n)
                    cdef GEN _n = (<Gen>n).g
                    sig_on()
                    setrand(_n)
                    clear_stack()
            <BLANKLINE>
            >>> G.handle_pari_function("bernvec",
            ...     cname="bernvec", prototype="L",
            ...     help="bernvec(x): this routine is obsolete, use bernfrac repeatedly.",
            ...     obsolete="2007-03-30",
            ...     **{"class":"basic", "section":"transcendental"})
                GEN bernvec(long)
                def bernvec(self, long x):
                    r'''
                    This routine is obsolete, kept for backward compatibility only.
                    '''
                    from warnings import warn
                    warn('the PARI/GP function bernvec is obsolete (2007-03-30)', DeprecationWarning)
                    sig_on()
                    cdef GEN _ret = bernvec(x)
                    return new_gen(_ret)
            <BLANKLINE>
        """
        try:
            args, ret = parse_prototype(prototype, help)
        except NotImplementedError:
            return  # Skip unsupported prototype codes

        doc = get_rest_doc(function)

        self.write_declaration(cname, args, ret, self.decl_file)

        if len(args) > 0 and isinstance(args[0], PariArgumentGEN):
            # If the first argument is a GEN, write a method of the
            # Gen class.
            self.write_method(function, cname, args, ret, args,
                    self.gen_file, doc, obsolete)

        # In any case, write a method of the Pari class.
        # Parse again with an extra "self" argument.
        args, ret = parse_prototype(prototype, help, [PariInstanceArgument()])
        self.write_method(function, cname, args, ret, args[1:],
                self.instance_file, doc, obsolete)

    def write_declaration(self, cname, args, ret, file):
        """
        Write a .pxd declaration of a PARI library function.

        INPUT:

        - ``cname`` -- name of the PARI C library call

        - ``args``, ``ret`` -- output from ``parse_prototype``

        - ``file`` -- a file object where the declaration should be
          written to
        """
        args = ", ".join(a.ctype() for a in args)
        s = '    {ret} {function}({args})'.format(ret=ret.ctype(), function=cname, args=args)
        print(s, file=file)

    def write_method(self, function, cname, args, ret, cargs, file, doc, obsolete):
        """
        Write Cython code with a method to call one PARI function.

        INPUT:

        - ``function`` -- name for the method

        - ``cname`` -- name of the PARI C library call

        - ``args``, ``ret`` -- output from ``parse_prototype``,
          including the initial args like ``self``

        - ``cargs`` -- like ``args`` but excluding the initial args

        - ``file`` -- a file object where the code should be written to

        - ``doc`` -- the docstring for the method

        - ``obsolete`` -- if ``True``, a deprecation warning will be
          given whenever this method is called
        """
        doc = doc.replace("\n", "\n        ")  # Indent doc

        protoargs = ", ".join(a.prototype_code() for a in args)
        callargs = ", ".join(a.call_code() for a in cargs)

        s = "    def {function}({protoargs}):\n"
        if doc:
            # Use triple single quotes to make it easier to doctest
            # this within triply double quoted docstrings.
            s += "        r'''\n        {doc}\n        '''\n"
        # Warning for obsolete functions
        if obsolete:
            s += "        from warnings import warn\n"
            s += "        warn('the PARI/GP function {function} is obsolete ({obsolete})', DeprecationWarning)\n"
        # Warning for undocumented arguments
        for a in args:
            s += a.deprecation_warning_code(function)
        for a in args:
            s += a.convert_code()
        s += "        sig_on()\n"
        s += ret.assign_code("{cname}({callargs})")
        s += ret.return_code()

        s = s.format(function=function, protoargs=protoargs, cname=cname, callargs=callargs, doc=doc, obsolete=obsolete)
        print(s, file=file)

    def __call__(self):
        """
        Top-level function to generate the auto-generated files.
        """
        D = read_pari_desc()
        D = sorted(D.values(), key=lambda d: d['function'])
        sys.stdout.write("Generating PARI functions:")

        self.gen_file = io.open(self.gen_filename + '.tmp', 'w', encoding='utf-8')
        self.gen_file.write(gen_banner)
        self.instance_file = io.open(self.instance_filename + '.tmp', 'w', encoding='utf-8')
        self.instance_file.write(instance_banner)
        self.decl_file = io.open(self.decl_filename + '.tmp', 'w', encoding='utf-8')
        self.decl_file.write(decl_banner)

        # Check for availability of hi-res SVG plotting. This requires
        # PARI-2.10 or later.
        have_plot_svg = False

        for v in D:
            func = v["function"]
            if self.can_handle_function(**v):
                sys.stdout.write(" %s" % func)
                sys.stdout.flush()
                self.handle_pari_function(**v)
                if func == "plothraw":
                    have_plot_svg = True
            else:
                sys.stdout.write(" (%s)" % func)
        sys.stdout.write("\n")

        self.instance_file.write("DEF HAVE_PLOT_SVG = {}".format(have_plot_svg))

        self.gen_file.close()
        self.instance_file.close()
        self.decl_file.close()

        # All done? Let's commit.
        os.rename(self.gen_filename + '.tmp', self.gen_filename)
        os.rename(self.instance_filename + '.tmp', self.instance_filename)
        os.rename(self.decl_filename + '.tmp', self.decl_filename)
