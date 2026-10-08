"""Attempt 1: final form pool (ordered cheapest first) after exclusions.

Rules on top of pool.py (max zipf < 3.0 in 11 languages, space-prefixed cost measured in context):
- one form per case-folded spelling (no minimal pairs that differ only in case)
- no internal capitals (QString, GPIO, FIXME ...)
- English zipf < 2.5 (removes most real English words such as retry, lookup, backend)
- hand blacklist of code identifiers / English words / abbreviations that survive the frequency filter
"""
from __future__ import annotations

import json
from pathlib import Path

from wordfreq import zipf_frequency

HERE = Path(__file__).resolve().parent

BLACKLIST = set("""
kwargs dtype attrs javax retval argc argv typeof typedef readonly sizeof utils params cref datetime numpy addr uuid
fmt foreach ctx cfg iterator regex printf operand wx idx func dict buf attr bool tuple indent utf ptr uid rhs lhs
opts cmd req obj onclick unset async enum args logger struct init vec py href usize xmlns pytest jsonify nullptr
outfile sklearn argparse fontsize queryset fprintf sprintf colspan unittest errno bcrypt recv memcpy fname elseif
filepath strlen pygame inplace regexp nullable stderr iterable mkdir typename bgcolor charset stdin concat valign
pathname stmt varchar csrf dword inode prefs endif stdout nums polys yaml opcode chk oauth datatype configs caret
lastname globals newline eof postgres userid jwt dbo lbl sqlite hostname sqrt tooltip centroid dropdown readme endl
recurs rsp tuples qty xor checksum editable coords renderer frm freq reducer gid upd mapper rng smtp scoped sess
deque hashed elt checkbox epochs subnet markdown gtk pwd mutable schemas preds pkg verbose querying debugger psz
resize repr iterate computes timezone mappings vocab fft shader buffered gpio uint fixme qstring gfp parsed bitmap
json bool calc prev eval retry lookup backend endpoint embed encode cached parser filename datasets callback
nslog impl expr alloc dyn sched maint awk goog hasn hadn shouldn couldn wouldn wasn isn doesn didn aren weren
tmp src dst msg ret val arr len str int num cnt ctr idx ndx inc dec sep tbl col pos fn cb el btn img nav
bitwise uint8 int32 malloc calloc realloc ifdef ifndef pragma lambda kwarg vars pid tid gui cli api url uri sql
http https html css xml csv pdf rgb rgba hex utc gmt usd eur gbp
frontend taxp xmin ylim ymax ymin mathf bbox geom noqa padx objs qry indx nargs pname clazz ctypes errmsg fclose infile listop logits memset pprint pyplot shutil strcmp strcpy xlabel xrange ylabel asyncio dirname figsize getattr hasattr hashlib ndarray pathlib pthread randint rowspan setattr webhook basename deepcopy lateinit noexcept onchange sockaddr tabindex tempfile bson gson fopen qgs eslint enqueue gettext xhr grpc drawable recurse cmds textarea userdata atoi gint undef readline prepend uname fullname mmap bpy cmap plist scanf nowrap imgs xmax navbar scrapy println txn passwd vtk libc accessor irq xmm unlink mutex inorder deps gzip eax writable msgs fld callable postfix dirs uart xpath textbox rtn jdbc webpack ctxt subj endian unary scaler builtin clf subtree glm llvm updater pyl sortable jq axios servlet pady parses operands ansible dbg viewport lorem amet ipsum axs cwd literals testcase gcd unk ldap thresh tensors truncate srv firebase tgt radians laravel dims vmax tty hashes mse sanitize codecs pairwise svc spline clr ethers jitter disjoint ffi rnd rst captcha svn opr mpl baud vlan npm rpc tst dto itr tpl nbr tqdm urllib tkinter scipy iframe voxel gql cljs glfw hwnd ierr knex outf rval setw tmpl aload datab datap etree fread funcs gchar htons hypot keyof layui lname metav minib pstmt serde ssize tbody wchar dotenv fflush fwrite getenv intval ipairs multer nameof nargin okhttp perror strcat strdup strpos strtok mockito dequeue freopen getline jobject strconv timeval uintptr clearfix debounce gboolean offsetof pageable protobuf snprintf strerror varargin getchar ngx ioctl jint tokenize logfile softmax ulong noop affero mixins wasm cname symlink junit zlib splitted jsx favicon xsi assh filesize ctor graphql structs forall chmod wget submenu syslog isset coeff bigint retries ints inds scor uniq truncate quam eius velit noen selv godt meget hver
lxml javafx zmq xunit annotate insn ctype parms blockly xpos autobi doctr apont liik ssid jmp icmp xls edx itm
imap posix emacs trx prm qed kotlin ryzen arial insets swiper addons perms gfx mdi gdb svm akka fifo monad creds millis
defs fabs errs mux wnd sib osm pwm seeder dbl ctl dbc xb ofs hx drv gsl gbc tsl mip qw unsub smarty aio itk accel distr
resized reorder chooser paginate preload zipcode reducers uploader resizing shaders getters indexer verifier notifier
waypoint functor subscript appending clickable malformed whitelist heatmap subtotal typings bufsize cmdline zipfile
syscall sigmoid metavar multiline androidx datasource datastore palindrome xamarin magento runnable glyphicon mongodb
decrement unregister discriminator homosex prostit substr compat ceil dbus signin delim jav optim decl
myfile cmake mqtt rospy protoc tolua clk ql repl expl execut enh hect abol atten carg vuel merg annot
htt dbname lodash openid pdata ecx cef edir xlim cdecl consts intptr mlx astore ebx fgets strstr subdir mpz hbox
arcpy dicts ncols nrows rects maxlen pulumi stddev vmin vbox theano hmac pyg toks gdk diffs rnn hdf dct rpt heapq isize
vnode assms keyst srand uchar arity lexer pylint atof intf ktor muham massac lesb erot homic suic misog answ valg
iface inp coef paramet pyt cowork
""".split())


_PREFIXES: set[str] | None = None


def frequent_prefixes() -> set[str]:
    """proper prefixes (len >= 7) of words with zipf >= 3.0 in any of the 11 languages."""
    global _PREFIXES
    if _PREFIXES is None:
        from wordfreq import top_n_list
        out: set[str] = set()
        for lang in ["en", "es", "de", "fr", "it", "pt", "nl", "tr", "id", "pl", "sv"]:
            for w in top_n_list(lang, 60000):
                if zipf_frequency(w, lang) < 3.0:
                    break
                for i in range(7, len(w)):
                    out.add(w[:i])
        _PREFIXES = out
    return _PREFIXES


def load_pool(path: Path | None = None) -> list[dict]:
    """Ordered pool. Forms of 7+ letters must be truncated fragments (proper prefix of a frequent word in one of the
    11 languages): complete long tokens are almost always real words or code identifiers (serializer, localhost)."""
    prefixes = frequent_prefixes()
    rows = json.loads((path or HERE / "pool_attempt_1.json").read_text())
    seen: set[str] = set()
    out = []
    for r in rows:
        f = r["form"]
        k = f.lower()
        if k in seen:
            continue
        if any(c.isupper() for c in f[1:]):
            continue
        if k in BLACKLIST:
            continue
        if zipf_frequency(k, "en") >= 2.5:
            continue
        if len(k) >= 7 and k not in prefixes:
            continue
        seen.add(k)
        out.append(r)
    return out


if __name__ == "__main__":
    import statistics
    pool = load_pool()
    names = list(pool[0]["cost"])
    print("pool", len(pool), "single in all 7:", sum(1 for r in pool if r["n_single"] == 7))
    for a, b in [(0, 200), (200, 800), (800, 1400), (1400, 2100), (0, 2100)]:
        seg = pool[a:b]
        print(f"  ranks {a}-{b}", " ".join(f"{n}={statistics.mean(r['cost'][n] for r in seg):.2f}" for n in names))
    print(" ".join(r["form"] for r in pool[:2200]))
