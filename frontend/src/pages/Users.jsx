import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../api";
import { Button, Modal, ErrorBox } from "../components/ui";

function UserModal({ user, onClose, saved }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      await api("/users" + (user ? "/" + user.id : ""), {
        method: user ? "PATCH" : "POST",
        body: {
          name: f.get("name"),
          email: f.get("email"),
          password: f.get("password"),
          role: f.get("role"),
          active: f.get("active") === "on",
        },
      });
      await saved();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={user ? "Editar cuenta" : "Crear una cuenta"}
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <label>
          Nombre
          <input
            name="name"
            required
            maxLength={100}
            defaultValue={user?.name}
          />
        </label>
        <label>
          Correo electrónico
          <input
            name="email"
            type="email"
            required
            defaultValue={user?.email}
          />
        </label>
        <label>
          {user ? "Nueva contraseña (opcional)" : "Contraseña inicial"}
          <input
            name="password"
            type="password"
            required={!user}
            minLength={10}
            maxLength={256}
            autoComplete="new-password"
          />
          <small>Mínimo 10 caracteres.</small>
        </label>
        <label>
          Rol
          <select name="role" defaultValue={user?.role || "owner"}>
            <option value="owner">Dueño del anuncio</option>
            <option value="admin">Administrador</option>
          </select>
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            name="active"
            defaultChecked={user?.active ?? true}
          />
          Cuenta activa
        </label>
        <ErrorBox message={error} />
        <div className="modalactions">
          <Button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button disabled={busy}>
            {busy ? "Guardando…" : "Guardar cuenta"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export { UserModal };
