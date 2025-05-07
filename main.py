import streamlit as st
import oracledb
from book_actions import (
    disponibilidad_libro, 
    donar_libro, 
    intercambiar_libro, 
    consultar_tabla, 
    galeria_libros_disponibles, 
    subir_imagen_ejemplar,
    informacion_usuario,
    intercambios_pendientes_usuario
)
user_db = "GRUPO2"
password_db = "TEAM2"
dsn = oracledb.makedsn("localhost", 1521, service_name="FREEPDB1")

try:
    connection = oracledb.connect(user=user_db, password=password_db, dsn=dsn)
    st.sidebar.success("Conexión exitosa a Oracle")

    if st.session_state.get("logged_in"):
        if st.sidebar.button("Cerrar Sesión"):
            st.session_state.clear()
            st.experimental_rerun()

    if "logged_in" not in st.session_state:
        st.title("Inicio de Sesión")
        rol = st.radio("Seleccione Rol", ["Admin", "User"])
        if rol == "Admin":
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.button("Entrar"):
                if username == "admin" and password == "admin":
                    st.session_state.logged_in = True
                    st.session_state.role = "admin"
                else:
                    st.error("Credenciales incorrectas.")
        else:
            user_id = st.text_input("Ingrese su ID de Usuario")
            if st.button("Entrar"):
                if user_id.isdigit():
                    cursor = connection.cursor()
                    cursor.execute("SELECT idUsuario FROM Usuario WHERE idUsuario = :u_id", {"u_id": int(user_id)})
                    row = cursor.fetchone()
                    cursor.close()
                    if row:
                        st.session_state.logged_in = True
                        st.session_state.role = "user"
                        st.session_state.user_id = user_id
                    else:
                        st.error("El usuario no existe.")
                else:
                    st.error("El ID debe ser un valor numérico.")

    if st.session_state.get("logged_in"):
        if st.session_state.role == "admin":
            option = st.sidebar.radio("Seleccione acción", ["Subir Imagen Libro", "Consultar Tablas"])
        else:
            option = st.sidebar.radio("Seleccione acción", 
                                      ["Disponibilidad Libro", "Donar Libro", "Intercambiar Libro", "Galería Libros Disponibles", "Informacion Usuario", "Intercambios Pendientes"])
        
        if st.session_state.role == "admin":
            if option == "Subir Imagen Libro":
                subir_imagen_ejemplar(connection)
            elif option == "Consultar Tablas":
                consultar_tabla(connection)
        else:
            if option == "Disponibilidad Libro":
                disponibilidad_libro(connection)
            elif option == "Donar Libro":
                donar_libro(connection)  
            elif option == "Intercambiar Libro":
                intercambiar_libro(connection)
            elif option == "Galería Libros Disponibles":
                galeria_libros_disponibles(connection)
            elif option == "Informacion Usuario":
                informacion_usuario(connection)
            elif option == "Intercambios Pendientes":
                intercambios_pendientes_usuario(connection)
        
except Exception as e:
    st.error(f"Error: {e}")
finally:
    if 'connection' in locals() and connection:
        connection.close()