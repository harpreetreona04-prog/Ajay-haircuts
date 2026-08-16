import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  addMonths,
  subMonths,
  format,
  isSameMonth,
  isToday,
} from "date-fns";
import { SERVICES } from "../data/site";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ADMIN_PASSWORD = process.env.REACT_APP_ADMIN_PASSWORD;

// Sent as X-Admin-Key on owner-only endpoints. The backend only enforces
// this if ADMIN_API_KEY is set in its own .env — see server.py. Setting
// both env vars to the same value is what actually locks the API down;
// the login screen alone only gates the dashboard UI, not the API itself.
const adminHeaders = () =>
  ADMIN_PASSWORD ? { "X-Admin-Key": ADMIN_PASSWORD } : {};

const todayStr = () => format(new Date(), "yyyy-MM-dd");
const toDateStr = (d) => format(d, "yyyy-MM-dd");

// "09:00 AM" / "01:30 PM" -> minutes since midnight, so bookings sort in
// actual chronological order instead of alphabetically (which would put
// "01:00 PM" before "09:00 AM" since '1' < '9').
const timeToMinutes = (t) => {
  const m = /^(\d{1,2}):(\d{2})\s*(AM|PM)$/i.exec((t || "").trim());
  if (!m) return 0;
  let hours = parseInt(m[1], 10) % 12;
  if (m[3].toUpperCase() === "PM") hours += 12;
  return hours * 60 + parseInt(m[2], 10);
};

const WALKIN_SERVICE = "Phone / Walk-in";
const SERVICE_OPTIONS = [WALKIN_SERVICE, ...SERVICES.map((s) => s.title)];

const durationForService = (service) =>
  SERVICES.find((s) => s.title === service)?.duration || 30;

const emptyForm = (date, time) => ({
  service: WALKIN_SERVICE,
  date: date || todayStr(),
  time: time || "",
  name: "",
  phone: "",
  notes: "",
  isBlock: false,
  blockDuration: 30,
});

export default function Admin() {
  const [allBookings, setAllBookings] = useState([]);
  const [loadingBookings, setLoadingBookings] = useState(false);

  const [month, setMonth] = useState(startOfMonth(new Date()));
  const [selectedDate, setSelectedDate] = useState(todayStr());
  const [showCancelled, setShowCancelled] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState("create"); // "create" | "edit"
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState("");
  const [rowBusyId, setRowBusyId] = useState("");

  const [closedDates, setClosedDates] = useState({}); // { "yyyy-MM-dd": reason }
  const [dayClosedBusy, setDayClosedBusy] = useState(false);

  const loadAllBookings = () => {
    setLoadingBookings(true);
    axios
      .get(`${API}/bookings`)
      .then(({ data }) => setAllBookings(Array.isArray(data) ? data : []))
      .catch(() => setAllBookings([]))
      .finally(() => setLoadingBookings(false));
  };

  const loadClosedDates = () => {
    axios
      .get(`${API}/closed-dates`)
      .then(({ data }) => {
        const map = {};
        (Array.isArray(data) ? data : []).forEach((d) => {
          map[d.date] = d.reason || "";
        });
        setClosedDates(map);
      })
      .catch(() => setClosedDates({}));
  };

  useEffect(() => {
    loadAllBookings();
    loadClosedDates();
  }, []);

  const countsByDate = useMemo(() => {
    const map = {};
    allBookings.forEach((b) => {
      if (b.status === "cancelled" || b.status === "completed") return; // badge only counts upcoming/active
      map[b.date] = (map[b.date] || 0) + 1;
    });
    return map;
  }, [allBookings]);

  const dayBookingsActive = useMemo(
    () =>
      allBookings
        .filter((b) => b.date === selectedDate && b.status !== "cancelled" && b.status !== "completed")
        .sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time)),
    [allBookings, selectedDate]
  );

  const dayBookingsCancelled = useMemo(
    () =>
      allBookings
        .filter((b) => b.date === selectedDate && b.status === "cancelled")
        .sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time)),
    [allBookings, selectedDate]
  );

  const dayBookingsCompleted = useMemo(
    () =>
      allBookings
        .filter((b) => b.date === selectedDate && b.status === "completed")
        .sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time)),
    [allBookings, selectedDate]
  );

  const calendarDays = useMemo(() => {
    const start = startOfWeek(startOfMonth(month));
    const end = endOfWeek(endOfMonth(month));
    const days = [];
    let cur = start;
    while (cur <= end) {
      days.push(cur);
      cur = addDays(cur, 1);
    }
    return days;
  }, [month]);

  // ----- Modal: slot fetching -----
  const fetchModalSlots = (opts) => {
    const { date, service, excludeId } = opts;
    if (!date) { setSlots([]); return; }
    setSlotsLoading(true);
    const params = { date, ignore_closed: true, admin: true, service };
    if (excludeId) params.exclude_id = excludeId;
    axios
      .get(`${API}/bookings/availability`, { params })
      .then(({ data }) => setSlots(data.slots || []))
      .catch(() => setSlots([]))
      .finally(() => setSlotsLoading(false));
  };

  // Blocks don't map to a real service, so we fetch the slot grid using the
  // walk-in default (30 min spacing) for display; the server-side overlap
  // check on submit uses the actual block duration and is what really
  // protects against double-booking.
  useEffect(() => {
    if (!modalOpen || !form.date) return;
    fetchModalSlots({
      date: form.date,
      service: form.isBlock ? WALKIN_SERVICE : form.service,
      excludeId: modalMode === "edit" ? editingId : null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modalOpen, form.date, form.service, form.isBlock]);

  const openCreateModal = (date, time) => {
    setModalMode("create");
    setEditingId(null);
    setForm(emptyForm(date, time));
    setModalError("");
    setModalOpen(true);
  };

  const openEditModal = (booking) => {
    setModalMode("edit");
    setEditingId(booking.id);
    setForm({
      service: booking.service,
      date: booking.date,
      time: booking.time,
      name: booking.name,
      phone: booking.phone === "N/A" ? "" : booking.phone,
      notes: booking.notes || "",
      isBlock: booking.status === "blocked",
      blockDuration: booking.duration_minutes || 30,
    });
    setModalError("");
    setModalOpen(true);
  };

  const closeModal = () => setModalOpen(false);

  const submitModal = async () => {
    if (!form.time) { setModalError("Pick a time slot."); return; }
    if (!form.name.trim()) { setModalError("Enter a customer name (or a reason if blocking)."); return; }

    setSubmitting(true);
    setModalError("");
    try {
      if (modalMode === "create") {
        await axios.post(
          `${API}/admin/bookings`,
          {
            service: form.isBlock ? "Blocked" : form.service,
            date: form.date,
            time: form.time,
            duration_minutes: form.isBlock ? Number(form.blockDuration) : undefined,
            name: form.name,
            phone: form.phone || "N/A",
            notes: form.notes,
            is_block: form.isBlock,
          },
          { headers: adminHeaders() }
        );
      } else {
        await axios.patch(
          `${API}/admin/bookings/${editingId}`,
          {
            service: form.isBlock ? "Blocked" : form.service,
            date: form.date,
            time: form.time,
            duration_minutes: form.isBlock ? Number(form.blockDuration) : undefined,
            name: form.name,
            phone: form.phone || "N/A",
            notes: form.notes,
            status: form.isBlock ? "blocked" : "confirmed",
          },
          { headers: adminHeaders() }
        );
      }
      setModalOpen(false);
      setSelectedDate(form.date);
      loadAllBookings();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setModalError(typeof detail === "string" ? detail : "Couldn't save that booking. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const cancelBooking = async (booking) => {
    const label = booking.status === "blocked" ? "unblock this time" : "cancel this booking";
    if (!window.confirm(`Are you sure you want to ${label}?`)) return;
    setRowBusyId(booking.id);
    try {
      await axios.delete(`${API}/admin/bookings/${booking.id}`, { headers: adminHeaders() });
      loadAllBookings();
    } catch (e) {
      alert("Couldn't complete that action. Please try again.");
    } finally {
      setRowBusyId("");
    }
  };

  const completeBooking = async (booking) => {
    setRowBusyId(booking.id);
    try {
      await axios.patch(
        `${API}/admin/bookings/${booking.id}`,
        { status: "completed" },
        { headers: adminHeaders() }
      );
      loadAllBookings();
    } catch (e) {
      alert("Couldn't mark that booking complete. Please try again.");
    } finally {
      setRowBusyId("");
    }
  };

  const isSelectedDateClosed = Object.prototype.hasOwnProperty.call(closedDates, selectedDate);

  const toggleSelectedDateClosed = async () => {
    setDayClosedBusy(true);
    try {
      if (isSelectedDateClosed) {
        await axios.delete(`${API}/admin/closed-dates/${selectedDate}`, { headers: adminHeaders() });
      } else {
        if (!window.confirm(`Block the whole day (${selectedDate}) — no customer will be able to book anything on it. Continue?`)) {
          setDayClosedBusy(false);
          return;
        }
        await axios.post(
          `${API}/admin/closed-dates`,
          { date: selectedDate, reason: "" },
          { headers: adminHeaders() }
        );
      }
      loadClosedDates();
    } catch (e) {
      alert("Couldn't update that date. Please try again.");
    } finally {
      setDayClosedBusy(false);
    }
  };

  return (
    <div style={styles.wrap}>
      <header style={styles.header}>
        <div style={styles.eyebrow}>Owner access</div>
        <h1 style={styles.h1}>Booking Dashboard</h1>
        <div style={styles.sub}>Ajay Haircut · Surrey, BC</div>
      </header>

      <div style={styles.panel}>
        <div style={styles.calendarHeader}>
          <button style={styles.navBtn} onClick={() => setMonth((m) => subMonths(m, 1))}>‹</button>
          <div style={styles.monthLabel}>{format(month, "MMMM yyyy")}</div>
          <button style={styles.navBtn} onClick={() => setMonth((m) => addMonths(m, 1))}>›</button>
        </div>

        <div style={styles.weekRow}>
          {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
            <div key={i} style={styles.weekDay}>{d}</div>
          ))}
        </div>

        <div style={styles.calendarGrid}>
          {calendarDays.map((d) => {
            const ds = toDateStr(d);
            const inMonth = isSameMonth(d, month);
            const count = countsByDate[ds] || 0;
            const isSelected = ds === selectedDate;
            const isTuesday = d.getDay() === 2;
            const isManuallyClosed = Object.prototype.hasOwnProperty.call(closedDates, ds);
            return (
              <button
                key={ds}
                onClick={() => setSelectedDate(ds)}
                style={{
                  ...styles.dayCell,
                  opacity: inMonth ? 1 : 0.35,
                  ...(isSelected ? styles.dayCellSelected : {}),
                  ...(isToday(d) && !isSelected ? styles.dayCellToday : {}),
                }}
              >
                <span style={{ ...styles.dayNum, color: isSelected ? "#fff" : "#1C2340" }}>{format(d, "d")}</span>
                {(isTuesday || isManuallyClosed) && <span style={styles.dayClosedTag}>closed</span>}
                {count > 0 && (
                  <span style={isSelected ? styles.dayCountSelected : styles.dayCount}>{count}</span>
                )}
              </button>
            );
          })}
        </div>

        <div style={styles.dayPanelHeader}>
          <div>
            <div style={styles.sectionTitle}>{format(new Date(selectedDate + "T00:00:00"), "EEEE, MMM d")}</div>
            <div style={styles.hint}>
              {loadingBookings ? "Loading..." : `${dayBookingsActive.length} booking${dayBookingsActive.length === 1 ? "" : "s"}`}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              style={isSelectedDateClosed ? styles.btnAddSecondary : styles.btnAddDanger}
              disabled={dayClosedBusy}
              onClick={toggleSelectedDateClosed}
            >
              {dayClosedBusy ? "..." : isSelectedDateClosed ? "Unblock day" : "Block whole day"}
            </button>
            <button style={styles.btnAdd} onClick={() => openCreateModal(selectedDate, "")}>
              + Add booking
            </button>
          </div>
        </div>

        {isSelectedDateClosed && (
          <div style={styles.closedNotice}>
            Shop marked closed for this date — customers can't book any time on it.
          </div>
        )}

        {dayBookingsActive.length === 0 ? (
          <div style={styles.hint}>No bookings for this date.</div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Time</th>
                <th style={styles.th}>Customer</th>
                <th style={styles.th}>Service</th>
                <th style={styles.th}>Phone</th>
                <th style={styles.th}></th>
              </tr>
            </thead>
            <tbody>
              {dayBookingsActive.map((b) => (
                <tr key={b.id}>
                  <td style={styles.td}>
                    {b.time}
                    <div style={styles.durationTag}>{b.duration_minutes || 30} min</div>
                  </td>
                  <td style={styles.td}>
                    {b.name}
                    {b.status === "blocked" && <div style={styles.blockedTag}>blocked</div>}
                  </td>
                  <td style={styles.td}>{b.service}</td>
                  <td style={styles.td}>{b.phone}</td>
                  <td style={{ ...styles.td, textAlign: "right", whiteSpace: "nowrap" }}>
                    <button style={styles.btnLinkSmall} onClick={() => openEditModal(b)}>Edit</button>
                    {b.status !== "blocked" && (
                      <button
                        style={styles.btnLinkSmall}
                        disabled={rowBusyId === b.id}
                        onClick={() => completeBooking(b)}
                      >
                        Complete
                      </button>
                    )}
                    <button
                      style={styles.btnLinkDanger}
                      disabled={rowBusyId === b.id}
                      onClick={() => cancelBooking(b)}
                    >
                      {rowBusyId === b.id ? "..." : b.status === "blocked" ? "Unblock" : "Cancel"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {dayBookingsCompleted.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <button
              style={styles.btnLinkSmall}
              onClick={() => setShowCompleted((s) => !s)}
            >
              {showCompleted ? "Hide" : "Show"} completed ({dayBookingsCompleted.length})
            </button>
            {showCompleted && (
              <table style={{ ...styles.table, marginTop: 8 }}>
                <thead>
                  <tr>
                    <th style={styles.th}>Time</th>
                    <th style={styles.th}>Customer</th>
                    <th style={styles.th}>Service</th>
                    <th style={styles.th}>Phone</th>
                  </tr>
                </thead>
                <tbody>
                  {dayBookingsCompleted.map((b) => (
                    <tr key={b.id} style={{ opacity: 0.75 }}>
                      <td style={styles.td}>
                        {b.time}
                        <div style={styles.durationTag}>{b.duration_minutes || 30} min</div>
                      </td>
                      <td style={styles.td}>
                        {b.name}
                        <div style={styles.completedTag}>completed</div>
                      </td>
                      <td style={styles.td}>{b.service}</td>
                      <td style={styles.td}>{b.phone}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {dayBookingsCancelled.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <button
              style={styles.btnLinkSmall}
              onClick={() => setShowCancelled((s) => !s)}
            >
              {showCancelled ? "Hide" : "Show"} cancelled ({dayBookingsCancelled.length})
            </button>
            {showCancelled && (
              <table style={{ ...styles.table, marginTop: 8 }}>
                <thead>
                  <tr>
                    <th style={styles.th}>Time</th>
                    <th style={styles.th}>Customer</th>
                    <th style={styles.th}>Service</th>
                    <th style={styles.th}>Phone</th>
                  </tr>
                </thead>
                <tbody>
                  {dayBookingsCancelled.map((b) => (
                    <tr key={b.id} style={{ opacity: 0.6 }}>
                      <td style={styles.td}>
                        {b.time}
                        <div style={styles.durationTag}>{b.duration_minutes || 30} min</div>
                      </td>
                      <td style={styles.td}>
                        {b.name}
                        <div style={styles.blockedTag}>cancelled</div>
                      </td>
                      <td style={{ ...styles.td, textDecoration: "line-through" }}>{b.service}</td>
                      <td style={styles.td}>{b.phone}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {modalOpen && (
        <div style={styles.modalOverlay} onClick={closeModal}>
          <div style={styles.modalCard} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              {modalMode === "create" ? "Add booking" : "Edit booking"}
            </div>

            <label style={styles.checkboxRow}>
              <input
                type="checkbox"
                checked={form.isBlock}
                onChange={(e) => setForm((f) => ({ ...f, isBlock: e.target.checked, time: "" }))}
              />
              Block this time (no customer)
            </label>

            {!form.isBlock && (
              <>
                <div style={styles.fieldLabel}>Service</div>
                <select
                  style={styles.select}
                  value={form.service}
                  onChange={(e) => setForm((f) => ({ ...f, service: e.target.value, time: "" }))}
                >
                  {SERVICE_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {s} · {durationForService(s) || 30} min
                    </option>
                  ))}
                </select>
              </>
            )}

            {form.isBlock && (
              <>
                <div style={styles.fieldLabel}>Duration (minutes)</div>
                <input
                  type="number"
                  min={5}
                  step={5}
                  style={styles.input2}
                  value={form.blockDuration}
                  onChange={(e) => setForm((f) => ({ ...f, blockDuration: e.target.value, time: "" }))}
                />
              </>
            )}

            <div style={styles.fieldLabel}>Date</div>
            <input
              type="date"
              style={styles.input2}
              value={form.date}
              onChange={(e) => setForm((f) => ({ ...f, date: e.target.value, time: "" }))}
            />

            <div style={styles.fieldLabel}>Time</div>
            {slotsLoading ? (
              <div style={styles.hint}>Loading slots...</div>
            ) : (
              <div style={styles.slotsGrid}>
                {slots.map((s) => {
                  const isThisSlot = s.time === form.time;
                  const usable = s.available || isThisSlot;
                  return (
                    <button
                      key={s.time}
                      disabled={!usable}
                      onClick={() => setForm((f) => ({ ...f, time: s.time }))}
                      style={isThisSlot ? styles.slotSelected : usable ? styles.slotOpen : styles.slotTaken}
                    >
                      {s.time}
                    </button>
                  );
                })}
              </div>
            )}

            <div style={styles.fieldLabel}>{form.isBlock ? "Reason" : "Customer name"}</div>
            <input
              type="text"
              style={styles.input2}
              placeholder={form.isBlock ? "e.g. Lunch break" : "Customer name"}
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />

            {!form.isBlock && (
              <>
                <div style={styles.fieldLabel}>Phone (optional)</div>
                <input
                  type="text"
                  style={styles.input2}
                  placeholder="Phone number"
                  value={form.phone}
                  onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                />
              </>
            )}

            <div style={styles.fieldLabel}>Notes (optional)</div>
            <textarea
              rows={2}
              style={{ ...styles.input2, resize: "none" }}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            />

            {modalError && <div style={styles.error}>{modalError}</div>}

            <div style={styles.modalActions}>
              <button style={styles.btnSecondary} onClick={closeModal}>Cancel</button>
              <button style={styles.btnPrimary} onClick={submitModal} disabled={submitting}>
                {submitting ? "Saving..." : modalMode === "create" ? "Add booking" : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  lockWrap: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#F5F3EF",
    fontFamily: "Inter, sans-serif",
  },
  lockBox: {
    background: "#fff",
    padding: "32px 28px",
    borderRadius: 12,
    boxShadow: "0 2px 12px rgba(28,35,64,0.08)",
    width: 300,
  },
  wrap: {
    maxWidth: 900,
    margin: "0 auto",
    padding: "32px 16px",
    fontFamily: "Inter, sans-serif",
    color: "#1C2340",
  },
  header: {
    background: "#1C2340",
    color: "#fff",
    padding: "24px 28px",
    borderRadius: "10px 10px 0 0",
  },
  eyebrow: {
    color: "#D4A24C",
    fontSize: 12,
    letterSpacing: 1.5,
    textTransform: "uppercase",
    fontWeight: 600,
  },
  h1: { fontSize: 24, marginTop: 4, fontWeight: 700 },
  sub: { color: "#B9BDD3", fontSize: 13, marginTop: 6 },
  panel: {
    background: "#fff",
    borderRadius: "0 0 10px 10px",
    padding: "24px 28px 28px",
    boxShadow: "0 2px 12px rgba(28,35,64,0.06)",
  },
  calendarHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  navBtn: {
    border: "1px solid #E7E3DA",
    background: "#fff",
    borderRadius: 8,
    width: 32,
    height: 32,
    fontSize: 16,
    cursor: "pointer",
  },
  monthLabel: { fontSize: 16, fontWeight: 700 },
  weekRow: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    marginBottom: 4,
  },
  weekDay: {
    textAlign: "center",
    fontSize: 11,
    color: "#8A8F9E",
    fontWeight: 600,
    padding: "4px 0",
  },
  calendarGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    gap: 4,
  },
  dayCell: {
    position: "relative",
    border: "1px solid #F0EEE8",
    background: "#fff",
    borderRadius: 8,
    height: 52,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    padding: 4,
  },
  dayCellSelected: {
    border: "1px solid #1C2340",
    background: "#1C2340",
  },
  dayCellToday: {
    border: "1px solid #D4A24C",
  },
  dayNum: { fontSize: 13, fontWeight: 600 },
  dayClosedTag: { fontSize: 9, color: "#B23A3A", marginTop: 1 },
  dayCount: {
    position: "absolute",
    top: 4,
    right: 4,
    fontSize: 9,
    background: "#D4A24C",
    color: "#1C2340",
    borderRadius: 8,
    padding: "1px 5px",
    fontWeight: 700,
  },
  dayCountSelected: {
    position: "absolute",
    top: 4,
    right: 4,
    fontSize: 9,
    background: "#D4A24C",
    color: "#1C2340",
    borderRadius: 8,
    padding: "1px 5px",
    fontWeight: 700,
  },
  dayPanelHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    margin: "24px 0 12px",
  },
  sectionTitle: { fontSize: 18, fontWeight: 700 },
  hint: { fontSize: 12, color: "#8A8F9E", marginTop: 6 },
  btnAdd: {
    padding: "8px 14px",
    background: "#1C2340",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
  },
  btnAddDanger: {
    padding: "8px 14px",
    background: "#fff",
    color: "#B23A3A",
    border: "1px solid #E7B8B8",
    borderRadius: 8,
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
  },
  btnAddSecondary: {
    padding: "8px 14px",
    background: "#fff",
    color: "#2F7D4F",
    border: "1px solid #BFE0CC",
    borderRadius: 8,
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
  },
  closedNotice: {
    background: "#FDEEEE",
    color: "#B23A3A",
    fontSize: 12,
    padding: "8px 12px",
    borderRadius: 8,
    marginBottom: 12,
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 14, marginTop: 8 },
  th: {
    textAlign: "left",
    fontSize: 11,
    textTransform: "uppercase",
    color: "#8A8F9E",
    padding: "8px 10px",
    borderBottom: "1px solid #E7E3DA",
  },
  td: { padding: "10px", borderBottom: "1px solid #F0EEE8", verticalAlign: "top" },
  durationTag: { fontSize: 11, color: "#8A8F9E", marginTop: 2 },
  blockedTag: {
    fontSize: 11,
    color: "#B23A3A",
    marginTop: 2,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  completedTag: {
    fontSize: 11,
    color: "#2F7D4F",
    marginTop: 2,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  btnLinkSmall: {
    border: "none",
    background: "none",
    color: "#1C2340",
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
    marginRight: 12,
  },
  btnLinkDanger: {
    border: "none",
    background: "none",
    color: "#B23A3A",
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
  },
  input: {
    width: "100%",
    padding: "10px 12px",
    border: "1px solid #E7E3DA",
    borderRadius: 8,
    fontSize: 14,
    margin: "16px 0 8px",
  },
  input2: {
    width: "100%",
    padding: "9px 11px",
    border: "1px solid #E7E3DA",
    borderRadius: 8,
    fontSize: 14,
    marginBottom: 12,
    boxSizing: "border-box",
  },
  select: {
    width: "100%",
    padding: "9px 11px",
    border: "1px solid #E7E3DA",
    borderRadius: 8,
    fontSize: 14,
    marginBottom: 12,
    background: "#fff",
  },
  fieldLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    color: "#8A8F9E",
    fontWeight: 600,
    marginBottom: 4,
  },
  checkboxRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 16,
    cursor: "pointer",
  },
  slotsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 6,
    marginBottom: 12,
    maxHeight: 180,
    overflowY: "auto",
  },
  slotOpen: {
    border: "1px solid #E7E3DA",
    borderRadius: 6,
    padding: "8px 4px",
    fontSize: 12,
    fontWeight: 500,
    background: "#fff",
    cursor: "pointer",
  },
  slotTaken: {
    border: "1px solid #F0EEE8",
    borderRadius: 6,
    padding: "8px 4px",
    fontSize: 12,
    fontWeight: 500,
    background: "#F5F3EF",
    color: "#B9BDD3",
    textDecoration: "line-through",
    cursor: "not-allowed",
  },
  slotSelected: {
    border: "1px solid #1C2340",
    borderRadius: 6,
    padding: "8px 4px",
    fontSize: 12,
    fontWeight: 600,
    background: "#1C2340",
    color: "#fff",
    cursor: "pointer",
  },
  error: { color: "#B23A3A", fontSize: 12, marginBottom: 8 },
  btnPrimary: {
    padding: "10px 18px",
    background: "#1C2340",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnSecondary: {
    padding: "10px 18px",
    background: "#fff",
    color: "#1C2340",
    border: "1px solid #E7E3DA",
    borderRadius: 8,
    fontWeight: 600,
    cursor: "pointer",
  },
  modalOverlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(28,35,64,0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
    zIndex: 50,
  },
  modalCard: {
    background: "#fff",
    borderRadius: 12,
    padding: 24,
    width: 380,
    maxHeight: "90vh",
    overflowY: "auto",
    boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
  },
  modalHeader: { fontSize: 17, fontWeight: 700, marginBottom: 16 },
  modalActions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 8,
  },
};
