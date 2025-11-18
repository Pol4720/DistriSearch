import streamlit as st
import pandas as pd
from typing import Optional
from utils.api_client import ApiClient
from datetime import datetime

class AuthManager:
    """Gestor de autenticación para la aplicación."""

    def __init__(self, api_client: ApiClient):
        self.api = api_client

    def login_page(self) -> Optional[Dict]:
        """Página de inicio de sesión."""
        st.markdown("## 🔐 Iniciar Sesión")

        with st.form("login_form"):
            username = st.text_input("Usuario", placeholder="Ingresa tu nombre de usuario")
            password = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                login_btn = st.form_submit_button("🚀 Iniciar Sesión", use_container_width=True)
            with col2:
                register_btn = st.form_submit_button("📝 Registrarse", use_container_width=True)

        if login_btn:
            if not username or not password:
                st.error("Por favor, completa todos los campos.")
                return None

            try:
                with st.spinner("Iniciando sesión..."):
                    result = self.api.login_user(username, password)
                    st.success("¡Inicio de sesión exitoso!")
                    st.rerun()
                    return result
            except Exception as e:
                st.error(f"Error al iniciar sesión: {str(e)}")
                return None

        if register_btn:
            st.session_state.show_register = True
            st.rerun()

        return None

    def register_page(self) -> Optional[Dict]:
        """Página de registro."""
        st.markdown("## 📝 Registro de Usuario")

        with st.form("register_form"):
            username = st.text_input("Usuario", placeholder="Elige un nombre de usuario")
            email = st.text_input("Email", placeholder="tu@email.com")
            password = st.text_input("Contraseña", type="password", placeholder="Elige una contraseña segura")
            confirm_password = st.text_input("Confirmar Contraseña", type="password", placeholder="Repite la contraseña")

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                register_btn = st.form_submit_button("✅ Registrarse", use_container_width=True)
            with col2:
                back_btn = st.form_submit_button("⬅️ Volver", use_container_width=True)

        if register_btn:
            if not all([username, email, password, confirm_password]):
                st.error("Por favor, completa todos los campos.")
                return None

            if password != confirm_password:
                st.error("Las contraseñas no coinciden.")
                return None

            if len(password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
                return None

            try:
                with st.spinner("Registrando usuario..."):
                    result = self.api.register_user(username, email, password)
                    st.success("¡Usuario registrado exitosamente!")
                    st.session_state.show_register = False
                    st.rerun()
                    return result
            except Exception as e:
                st.error(f"Error al registrar usuario: {str(e)}")
                return None

        if back_btn:
            st.session_state.show_register = False
            st.rerun()

        return None

class TaskManager:
    """Gestor de tareas para la aplicación."""

    def __init__(self, api_client: ApiClient):
        self.api = api_client

    def dashboard(self):
        """Dashboard principal de tareas."""
        st.markdown("## 📋 Mis Tareas")

        # Estadísticas rápidas
        try:
            tasks = self.api.get_user_tasks()
            total_tasks = len(tasks)
            pending_tasks = len([t for t in tasks if t['status'] == 'pending'])
            completed_tasks = len([t for t in tasks if t['status'] == 'completed'])
            in_progress_tasks = len([t for t in tasks if t['status'] == 'in_progress'])

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total", total_tasks)
            with col2:
                st.metric("Pendientes", pending_tasks)
            with col3:
                st.metric("En Progreso", in_progress_tasks)
            with col4:
                st.metric("Completadas", completed_tasks)

        except Exception as e:
            st.error(f"Error al cargar estadísticas: {str(e)}")
            return

        # Crear nueva tarea
        with st.expander("➕ Crear Nueva Tarea", expanded=False):
            self.create_task_form()

        # Lista de tareas
        st.markdown("### 📝 Lista de Tareas")
        self.display_tasks(tasks)

    def create_task_form(self):
        """Formulario para crear nueva tarea."""
        with st.form("create_task_form"):
            title = st.text_input("Título de la tarea", placeholder="Ingresa el título")
            description = st.text_area("Descripción (opcional)", placeholder="Describe la tarea...", height=100)

            col1, col2 = st.columns([1, 3])
            with col1:
                submit_btn = st.form_submit_button("✅ Crear Tarea", use_container_width=True)

            if submit_btn:
                if not title.strip():
                    st.error("El título es obligatorio.")
                    return

                try:
                    with st.spinner("Creando tarea..."):
                        self.api.create_task(title.strip(), description.strip() if description else None)
                        st.success("¡Tarea creada exitosamente!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al crear tarea: {str(e)}")

    def display_tasks(self, tasks: list):
        """Muestra la lista de tareas."""
        if not tasks:
            st.info("No tienes tareas aún. ¡Crea tu primera tarea!")
            return

        # Filtros
        col1, col2 = st.columns([2, 1])
        with col1:
            status_filter = st.selectbox(
                "Filtrar por estado",
                ["Todas", "Pendientes", "En Progreso", "Completadas"],
                index=0
            )
        with col2:
            sort_by = st.selectbox(
                "Ordenar por",
                ["Fecha de creación", "Título", "Estado"],
                index=0
            )

        # Aplicar filtros
        filtered_tasks = tasks
        if status_filter != "Todas":
            status_map = {
                "Pendientes": "pending",
                "En Progreso": "in_progress",
                "Completadas": "completed"
            }
            filtered_tasks = [t for t in tasks if t['status'] == status_map[status_filter]]

        # Ordenar
        if sort_by == "Fecha de creación":
            filtered_tasks.sort(key=lambda x: x['created_at'], reverse=True)
        elif sort_by == "Título":
            filtered_tasks.sort(key=lambda x: x['title'].lower())
        elif sort_by == "Estado":
            status_order = {"pending": 0, "in_progress": 1, "completed": 2}
            filtered_tasks.sort(key=lambda x: status_order.get(x['status'], 3))

        # Mostrar tareas
        for task in filtered_tasks:
            self.display_task_card(task)

    def display_task_card(self, task: dict):
        """Muestra una tarjeta individual de tarea."""
        status_colors = {
            "pending": "🟡",
            "in_progress": "🔵",
            "completed": "🟢"
        }

        status_labels = {
            "pending": "Pendiente",
            "in_progress": "En Progreso",
            "completed": "Completada"
        }

        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**{task['title']}**")
                if task.get('description'):
                    st.caption(task['description'][:100] + "..." if len(task['description']) > 100 else task['description'])

                created_date = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00')).strftime('%d/%m/%Y %H:%M')
                st.caption(f"Creada: {created_date}")

            with col2:
                current_status = task['status']
                new_status = st.selectbox(
                    f"{status_colors[current_status]} {status_labels[current_status]}",
                    ["pending", "in_progress", "completed"],
                    index=["pending", "in_progress", "completed"].index(current_status),
                    key=f"status_{task['id']}",
                    label_visibility="collapsed"
                )

                if new_status != current_status:
                    try:
                        self.api.update_task(task['id'], new_status)
                        st.success("Estado actualizado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar: {str(e)}")

            with col3:
                if st.button("🗑️", key=f"delete_{task['id']}", help="Eliminar tarea"):
                    try:
                        self.api.delete_task(task['id'])
                        st.success("Tarea eliminada!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {str(e)}")

            st.divider()