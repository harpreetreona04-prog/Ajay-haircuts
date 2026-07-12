import { useState, useEffect } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ADMIN_PASSWORD = process.env.REACT_APP_ADMIN_PASSWORD;

const todayStr = () => new Date().toISOString().split("T")[0];

export default function Admin() {
  const [unlocked, setUnlocked] = useState(
    sessionStorage.getItem("admin_ok") === "1"
  );
  const [pwInput, setPwInput] = useState("");
  const [pwError, setPwError] = useState("");

  const [bookings, setBookings] = useState([]);
  const [loadingBookings, setLoadingBookings] = useState(false);

  const [date, setDate] = useState(todayStr());
  const [slots, setSlots] = useState([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [blocking, setBlocking] = useState("");

  const checkPassword = (e) => {
    e.preventDefault();
    if (pwInput === ADMIN_PASSWORD && ADMIN_PASSWORD) {
      sessionStorage.setItem("admin_ok", "1");
      setUnlocked(true);
      setPwError("");
    } else {
      setPwError("Wrong password. Try again.");
    }
  };

  const loadBookings = () => {
    setLoadingBookings(true);
    axios
      .get(`${API}/bookings`)
      .then(({ data }) => {
        const list = Array.isArray(data) ? data : data.bookings || [];
        list.sort((a, b) =>
          (a.date + a.time).localeCompare(b.date + b.time)
        );
        setBookings(list);
      })
      .catch(() => setBookings([]))
      .finally(() => setLoadingBookings(false));
  };

  const loadSlots = (d) => {
    setLoadingSlots(true);
    axios
      .get(`${API}/bookings/availability`, { params: { date: d } })
      .then(({ data }) => setSlots(data.slots || []))
      .catch(() => setSlots([]))
      .finally(() => setLoadingSlots(false));
  };

  useEffect(() => {
    if (unlocked) loadBookings();
  }, [unlocked]);

  useEffect(() => {
    if (unlocked) loadSlots(date);
  }, [unlocked, date]);

  const blockSlot = async (time) => {
    setBlocking(time);
    try {
      await axios.post(`${API}/bookings`, {
        service: "Blocked (phone/walk-in)",
        date,
        time,
        name: "Blocked slot",
        email: "owner@ajayhaircut.com",
        phone: "0000000000",
      });
      loadSlots(date);
      loadBookings();
    } catch (e) {
      alert("Couldn't block that slot. Please try again.");
    } finally {
      setBlocking("");
    }
  };

  if (!unlocked) {
    return (
      <div style={styles.lockWrap}>
        <form onSubmit={checkPassword} style={styles.lockBox}>
          <div style={styles.eyebrow}>Owner access</div>
          <h1 style={styles.h1}>Admin Login</h1>
          <input
            type="password"
            placeholder="Enter password"
            value={pwInput}
            onChange={(e) => setPwInput(e.target.value)}
            style={styles.input}
            autoFocus
          />
          {pwError && <div style={styles.error}>{pwError}</div>}
          <button type="submit" style={styles.btnPrimary}>
            Unlock
          </button>
        </form>
      </div>
    );
  }

  return (
    <div style={styles.wrap}>
      <header style={styles.header}>
        <div style={styles.eyebrow}>Owner access</div>
        <h1 style={styles.h1}>Booking Dashboard</h1>
        <div style={styles.sub}>Ajay Haircut · Surrey, BC</div>
      </header>

      <div style={styles.panel}>
        <div style={styles.sectionTitle}>Schedule</div>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={styles.dateInput}
        />
        <div style={styles.hint}>
          Tap an open slot to block it for a walk-in or phone booking.
        </div>

        {loadingSlots ? (
          <div style={styles.hint}>Loading slots...</div>
        ) : (
          <div style={styles.slotsGrid}>
            {slots.map((s) => (
              <button
                key={s.time}
                disabled={!s.available || blocking === s.time}
                onClick={() => blockSlot(s.time)}
                style={
                  s.available ? styles.slotOpen : styles.slotTaken
                }
              >
                {blocking === s.time ? "..." : s.time}
              </button>
            ))}
          </div>
        )}

        <div style={styles.sectionTitle}>Upcoming bookings</div>
        {loadingBookings ? (
          <div style={styles.hint}>Loading bookings...</div>
        ) : bookings.length === 0 ? (
          <div style={styles.hint}>No bookings yet.</div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Date</th>
                <th style={styles.th}>Time</th>
                <th style={styles.th}>Customer</th>
                <th style={styles.th}>Phone</th>
                <th style={styles.th}>Service</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b, i) => (
                <tr key={i}>
                  <td style={styles.td}>{b.date}</td>
                  <td style={styles.td}>{b.time}</td>
                  <td style={styles.td}>{b.name}</td>
                  <td style={styles.td}>{b.phone}</td>
                  <td style={styles.td}>{b.service}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
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
  sectionTitle: {
    fontSize: 18,
    fontWeight: 700,
    margin: "24px 0 12px",
  },
  dateInput: {
    padding: "8px 10px",
    border: "1px solid #E7E3DA",
    borderRadius: 8,
    fontSize: 14,
  },
  hint: { fontSize: 12, color: "#8A8F9E", marginTop: 10 },
  slotsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 10,
    marginTop: 14,
  },
  slotOpen: {
    border: "1px solid #E7E3DA",
    borderRadius: 8,
    padding: "12px 8px",
    fontSize: 13,
    fontWeight: 500,
    background: "#fff",
    cursor: "pointer",
  },
  slotTaken: {
    border: "1px solid #1C2340",
    borderRadius: 8,
    padding: "12px 8px",
    fontSize: 13,
    fontWeight: 500,
    background: "#1C2340",
    color: "#fff",
    cursor: "default",
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
  td: { padding: "10px", borderBottom: "1px solid #F0EEE8" },
  input: {
    width: "100%",
    padding: "10px 12px",
    border: "1px solid #E7E3DA",
    borderRadius: 8,
    fontSize: 14,
    margin: "16px 0 8px",
  },
  error: { color: "#B23A3A", fontSize: 12, marginBottom: 8 },
  btnPrimary: {
    width: "100%",
    padding: "10px",
    background: "#1C2340",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    fontWeight: 600,
    cursor: "pointer",
  },
};
