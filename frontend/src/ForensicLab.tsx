import { Database, FileStack, GitCompareArrows, Scissors, Trash2 } from "lucide-react";
import { ChangeEvent, useEffect, useState } from "react";

import {
  carveFile,
  correlateSelector,
  createInterestingRule,
  deleteInterestingRule,
  importHashSet,
  listHashSets,
  listInterestingRules,
  lookupHash,
} from "./api";
import type {
  CarveResult,
  CorrelationQueryResult,
  HashLookupResult,
  HashSetInfo,
  InterestingRule,
} from "./types";

type Tab = "hashsets" | "correlation" | "carving" | "rules";

const TABS: { id: Tab; label: string; icon: typeof Database }[] = [
  { id: "hashsets", label: "Hash sets", icon: Database },
  { id: "correlation", label: "Correlation", icon: GitCompareArrows },
  { id: "carving", label: "Carving", icon: Scissors },
  { id: "rules", label: "Rules", icon: FileStack },
];

function Err({ msg }: { msg: string }) {
  return msg ? <div className="forensics-error" role="alert">{msg}</div> : null;
}

// --- Hash sets ------------------------------------------------------------ #
function HashSets({ isAdmin }: { isAdmin: boolean }) {
  const [sets, setSets] = useState<HashSetInfo[]>([]);
  const [setName, setSetName] = useState("");
  const [category, setCategory] = useState<"notable" | "known_good">("notable");
  const [severity, setSeverity] = useState("high");
  const [hashes, setHashes] = useState("");
  const [lookupValue, setLookupValue] = useState("");
  const [lookupResult, setLookupResult] = useState<HashLookupResult | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = () => listHashSets().then(setSets).catch(() => undefined);
  useEffect(() => {
    refresh();
  }, []);

  async function onImport() {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const result = await importHashSet({ set_name: setName, category, severity, hashes });
      setHashes("");
      await refresh();
      setMessage(`Imported ${result.added} · duplicates ${result.skipped} · invalid ${result.invalid}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The hash set could not be imported.");
    } finally {
      setBusy(false);
    }
  }

  async function onLookup() {
    setError("");
    try {
      setLookupResult(await lookupHash(lookupValue.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The hash lookup could not be completed.");
    }
  }

  return (
    <div className="flab-body">
      <div className="flab-two">
        <div className="flab-block">
          <h4>Import known hashes</h4>
          {!isAdmin && <p className="flab-hint">Only an administrator can import hash sets.</p>}
          <input placeholder="Set name (for example, malware-2026)" value={setName} onChange={(e) => setSetName(e.target.value)} />
          <div className="flab-row">
            <select value={category} onChange={(e) => setCategory(e.target.value as "notable" | "known_good")}>
              <option value="notable">notable (known harmful)</option>
              <option value="known_good">known_good (known benign)</option>
            </select>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
              {["info", "low", "medium", "high", "critical"].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <textarea
            placeholder="One MD5, SHA-1, or SHA-256 per line; optional: hash, label"
            rows={5}
            value={hashes}
            onChange={(e) => setHashes(e.target.value)}
          />
          <button type="button" onClick={onImport} disabled={busy || !isAdmin || !setName.trim() || !hashes.trim()}>
            Import
          </button>
        </div>

        <div className="flab-block">
          <h4>Check a hash</h4>
          <input placeholder="md5 / sha1 / sha256" value={lookupValue} onChange={(e) => setLookupValue(e.target.value)} />
          <button type="button" onClick={onLookup} disabled={!lookupValue.trim()}>
            Search
          </button>
          {lookupResult && (
            <div className="flab-result">
              {lookupResult.matched ? (
                lookupResult.matches.map((m, i) => (
                  <div key={i} className={`flab-badge ${m.category}`}>
                    <strong>{m.set_name}</strong> · {m.category}/{m.severity} {m.label && `· ${m.label}`}
                  </div>
                ))
              ) : (
                <span className="flab-hint">No matches in registered hash sets.</span>
              )}
            </div>
          )}
        </div>
      </div>

      <Err msg={error} />
      {message && <div className="platform-inline-success" role="status">{message}</div>}

      <div className="flab-list">
        <h4>Registered sets</h4>
        {sets.length === 0 && <span className="flab-hint">No hash sets registered yet.</span>}
        {sets.map((s) => (
          <div key={`${s.set_name}-${s.category}`} className="flab-item">
            <span className={`flab-badge ${s.category}`}>{s.category}</span>
            <strong>{s.set_name}</strong>
            <span className="flab-count">{s.entries} entries</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Correlation ---------------------------------------------------------- #
function Correlation() {
  const [attrType, setAttrType] = useState("file_hash");
  const [value, setValue] = useState("");
  const [result, setResult] = useState<CorrelationQueryResult | null>(null);
  const [error, setError] = useState("");

  async function onQuery() {
    setError("");
    try {
      setResult(await correlateSelector(attrType, value.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The cross-investigation correlation could not be completed.");
    }
  }

  return (
    <div className="flab-body">
      <div className="flab-block">
        <h4>Has this selector appeared in another investigation?</h4>
        <div className="flab-row">
          <select value={attrType} onChange={(e) => setAttrType(e.target.value)}>
            {["file_hash", "email", "domain", "ip", "url", "handle", "crypto", "phone", "asn"].map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input placeholder="Selector value" value={value} onChange={(e) => setValue(e.target.value)} />
          <button type="button" onClick={onQuery} disabled={!value.trim()}>
            Correlate
          </button>
        </div>
      </div>

      <Err msg={error} />

      {result && (
        <div className="flab-list">
          <h4>
            {result.count} occurrence{result.count === 1 ? "" : "s"} of <code>{result.value}</code>
          </h4>
          {result.hits.map((h, i) => (
            <div key={i} className="flab-item">
              <span className="flab-badge">{h.attr_type}</span>
              <strong>{h.case_title}</strong>
              <span className="flab-count">{h.first_seen_at?.slice(0, 10)}</span>
            </div>
          ))}
          {result.count === 0 && <span className="flab-hint">This selector has not appeared in another investigation.</span>}
        </div>
      )}
    </div>
  );
}

// --- Carving -------------------------------------------------------------- #
function Carving({ caseId }: { caseId: string }) {
  const [result, setResult] = useState<CarveResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await carveFile(caseId, file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "File carving could not be completed. No artifact was added.");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  return (
    <div className="flab-body">
      <div className="flab-block">
        <h4>Recover embedded files from a carrier</h4>
        <p className="flab-hint">Choose a file to carve embedded ZIP, PDF, executable, or trailing data. Recovered artifacts are sealed as evidence.</p>
        <label className="forensics-drop">
          <Scissors size={18} />
          <span>{busy ? "Carving…" : "Choose a file to carve"}</span>
          <input type="file" onChange={onFile} disabled={busy || !caseId} hidden />
        </label>
      </div>

      <Err msg={error} />

      {result && (
        <div className="flab-list">
          <h4>{result.count} recovered artifact{result.count === 1 ? "" : "s"}</h4>
          {result.artifacts.map((a) => (
            <div key={a.source_id} className="flab-item">
              <span className="flab-badge">{a.carved_type}</span>
              <strong>@ {a.offset}</strong>
              <span className="flab-count">{a.size} B · {a.reason}</span>
              {a.hash_matches > 0 && <span className="flab-badge notable">notable hash</span>}
              {a.correlation_hits > 0 && <span className="flab-badge">correlated</span>}
            </div>
          ))}
          {result.count === 0 && <span className="flab-hint">No embedded files were found.</span>}
        </div>
      )}
    </div>
  );
}

// --- Interesting rules ---------------------------------------------------- #
function Rules({ isAdmin }: { isAdmin: boolean }) {
  const [rules, setRules] = useState<InterestingRule[]>([]);
  const [name, setName] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [types, setTypes] = useState("");
  const [extensions, setExtensions] = useState("");
  const [nameGlob, setNameGlob] = useState("");
  const [minEntropy, setMinEntropy] = useState("");
  const [error, setError] = useState("");

  const refresh = () => listInterestingRules().then(setRules).catch(() => undefined);
  useEffect(() => {
    refresh();
  }, []);

  async function onCreate() {
    setError("");
    try {
      await createInterestingRule({
        name,
        severity,
        types: types.split(",").map((s) => s.trim()).filter(Boolean),
        extensions: extensions.split(",").map((s) => s.trim()).filter(Boolean),
        name_glob: nameGlob.trim(),
        min_entropy: minEntropy ? Number(minEntropy) : null,
      });
      setName("");
      setTypes("");
      setExtensions("");
      setNameGlob("");
      setMinEntropy("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The interesting-file rule could not be created.");
    }
  }

  async function onDelete(id: string) {
    await deleteInterestingRule(id).catch(() => undefined);
    await refresh();
  }

  return (
    <div className="flab-body">
      <div className="flab-block">
        <h4>New interesting-file rule</h4>
        {!isAdmin && <p className="flab-hint">Only an administrator can create rules.</p>}
        <input placeholder="Rule name" value={name} onChange={(e) => setName(e.target.value)} />
        <div className="flab-row">
          <input placeholder="Types (png, zip, pe)" value={types} onChange={(e) => setTypes(e.target.value)} />
          <input placeholder="Extensions (exe, dll)" value={extensions} onChange={(e) => setExtensions(e.target.value)} />
        </div>
        <div className="flab-row">
          <input placeholder="Filename glob (*secret*)" value={nameGlob} onChange={(e) => setNameGlob(e.target.value)} />
          <input placeholder="Minimum entropy (7.5)" value={minEntropy} onChange={(e) => setMinEntropy(e.target.value)} />
          <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {["info", "low", "medium", "high", "critical"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <button type="button" onClick={onCreate} disabled={!isAdmin || !name.trim()}>
          Create rule
        </button>
      </div>

      <Err msg={error} />

      <div className="flab-list">
        <h4>Active rules</h4>
        {rules.length === 0 && <span className="flab-hint">No rules created yet.</span>}
        {rules.map((r) => (
          <div key={r.id} className="flab-item">
            <span className={`flab-badge sev-${r.severity}`}>{r.severity}</span>
            <strong>{r.name}</strong>
            <span className="flab-count">
              {[
                r.types.length ? `types: ${r.types.join("/")}` : "",
                r.extensions.length ? `ext: ${r.extensions.join("/")}` : "",
                r.name_glob ? `glob: ${r.name_glob}` : "",
                r.min_entropy != null ? `entropy≥${r.min_entropy}` : "",
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
            {isAdmin && (
              <button type="button" className="flab-del" onClick={() => onDelete(r.id)} aria-label={`Delete ${r.name}`}>
                <Trash2 size={14} />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ForensicLab({ caseId, isAdmin }: { caseId: string; isAdmin: boolean }) {
  const [tab, setTab] = useState<Tab>("hashsets");

  return (
    <section className="flab">
      <div className="flab-tabs">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" className={tab === id ? "flab-tab active" : "flab-tab"} onClick={() => setTab(id)}>
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {tab === "hashsets" && <HashSets isAdmin={isAdmin} />}
      {tab === "correlation" && <Correlation />}
      {tab === "carving" && <Carving caseId={caseId} />}
      {tab === "rules" && <Rules isAdmin={isAdmin} />}
    </section>
  );
}
