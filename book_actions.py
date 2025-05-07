import re, io
import streamlit as st
import pandas as pd
from PIL import Image


def disponibilidad_libro(connection):
    cursor = connection.cursor()
    search_option = st.selectbox("Buscar por:", ["Código", "Título"])
    if search_option == "Código":
        search_value = st.text_input("Ingresa el código del libro")
    else:
        search_value = st.text_input("Ingresa el título del libro")
        
    if st.button("Consultar Disponibilidad"):
        if not search_value.strip():
            st.error("Debes ingresar un valor de búsqueda.")
        else:
            try:
                if search_option == "Código":
                    query = """
                        SELECT L.idLibro, L.titulo, E.idEjemplar, E.estado
                        FROM Libro L 
                        JOIN Ejemplar E ON L.idLibro = E.idLibro
                        WHERE L.idLibro = :code
                          AND E.estado = 'posesion'
                    """
                    cursor.execute(query, code=search_value)
                else:
                    query = """
                        SELECT L.idLibro, L.titulo, E.idEjemplar, E.estado
                        FROM Libro L 
                        JOIN Ejemplar E ON L.idLibro = E.idLibro
                        WHERE LOWER(L.titulo) LIKE :title
                          AND E.estado = 'posesion'
                    """
                    cursor.execute(query, title=f"%{search_value.lower()}%")
                results = cursor.fetchall()
                if results:
                    st.success("El libro está disponible:")
                    st.table(results)
                else:
                    st.info("El libro no se encuentra disponible.")
            except Exception as ex:
                st.error(f"Error al consultar disponibilidad: {ex}")
            finally:
                cursor.close()

def donar_libro(connection):
    st.header("Donar Libro")
    if st.session_state.get("role") == "user":
        donor_id = st.session_state.user_id
        st.info(f"ID del Donante: {donor_id}")
    else:
        donor_id = st.text_input("ID del Donante")
        
    book_id = st.text_input("Código del Libro a donar")
    edition_id = st.text_input("Código de Edición del Libro")
    

    if st.button("Donar Libro"):
        if not donor_id.strip() or not book_id.strip() or not edition_id.strip():
            st.error("Todos los campos son obligatorios.")
            return
        if not re.match(r"^L\d{3}$", book_id):
            st.warning("El código del libro debe comenzar con 'L' y 3 dígitos (ejemplo: L001).")
            return
        elif not re.match(r"^ED\d{2}$", edition_id):
            st.warning("El código de edición debe comenzar con 'ED' y 2 dígitos (ejemplo: ED01).")
            return
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT NVL(MAX(TO_NUMBER(REGEXP_REPLACE(idDonacion, '[^0-9]', ''))), 0) FROM Donacion")
            donation_id = 'D' + str(cursor.fetchone()[0] + 1).zfill(3)
            cursor.execute("SELECT NVL(MAX(TO_NUMBER(REGEXP_REPLACE(idEjemplar, '[^0-9]', ''))), 0) FROM Ejemplar")
            new_ejemplar = 'E' + str(cursor.fetchone()[0] + 1).zfill(3)
            
            cursor.execute("""
                INSERT INTO Donacion (idDonacion, idUsuarioDonador, fechaRecepcion, estadoValidacion)
                VALUES (:donation_id, :donor_id, SYSDATE, 1)
            """, {"donation_id": donation_id, "donor_id": donor_id})
            
            cursor.execute("""
                INSERT INTO Ejemplar (idEjemplar, idLibro, idEdicion, caratula, estado)
                VALUES (:new_ejemplar, :book_id, :edition_id, empty_blob(), 'posesion')
            """, {"new_ejemplar": new_ejemplar, "book_id": book_id, "edition_id": edition_id})
            
            cursor.execute("""
                INSERT INTO DonacionEjemplar (idDonacion, idEjemplar)
                VALUES (:donation_id, :new_ejemplar)
            """, {"donation_id": donation_id, "new_ejemplar": new_ejemplar})
            

            cursor.execute("""
                INSERT INTO Inventario (idEjemplar, idAccion, fecha)
                VALUES (:new_ejemplar, 'donacion', SYSDATE)
            """, {"new_ejemplar": new_ejemplar})
            
            connection.commit()
            st.success("Libro donado exitosamente. Código de donación: " + donation_id)
        except Exception as ex:
            connection.rollback()
            st.error(f"Error al donar libro: {ex}")
        finally:
            cursor.close()

def intercambiar_libro(connection):
    st.header("Intercambiar Libro")

    if st.session_state.get("role") == "user":
        user_id = st.session_state.user_id
        st.info(f"ID del Usuario: {user_id}")
    else:
        user_id = st.text_input("ID del Usuario")
    


    selected = st.session_state.get("selected_intercambio", None)
    if selected:

        book_ofrecibido = st.text_input("Código del Libro ofrecido")

        edition_ofrecibido = st.text_input("Código de Edición del Libro ofrecido")
        exemplar_recibido = st.text_input("Código del Ejemplar a recibir", value=selected.get("idEjemplarRecibido", ""))
    else:

        book_ofrecibido = st.text_input("Código del Libro ofrecido")
        edition_ofrecibido = st.text_input("Código de Edición del Libro ofrecido")
        exemplar_recibido = st.text_input("Código del Ejemplar a recibir")
    

    tipo_intercambio = st.selectbox("Tipo de intercambio", ["temporal", "permanente"])
    fecha_fin_input = None
    if tipo_intercambio == "temporal":
        fecha_fin_input = st.date_input("Fecha Fin")
    
    
    if st.button("Realizar Intercambio"):
        if (not user_id.strip() or not book_ofrecibido.strip() or 
            not edition_ofrecibido.strip() or not exemplar_recibido.strip()):
            st.error("Todos los campos son obligatorios.")
            return
        if not re.match(r"^L\d{3}$", book_ofrecibido):
            st.warning("El código del libro ofrecido debe comenzar con 'L' seguido de 3 dígitos (ejemplo: L001).")
            return
        elif not re.match(r"^ED\d{2}$", edition_ofrecibido):
            st.warning("El código de edición del libro ofrecido debe comenzar con 'ED' seguido de 2 dígitos (ejemplo: ED01).")
            return
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT idLibro, idEdicion 
                FROM Ejemplar
                WHERE idEjemplar = :exemplar
                  AND estado = 'posesion'
            """, {"exemplar": exemplar_recibido})
            row = cursor.fetchone()
            if not row:
                st.error("El ejemplar a recibir no está en posesión.")
                return

            received_book, received_edition = row
            

            cursor.execute("""
                SELECT NVL(MAX(TO_NUMBER(REGEXP_REPLACE(idEjemplar, '[^0-9]', ''))), 0)
                FROM Ejemplar
            """)
            new_val = cursor.fetchone()[0]
            new_exemplar_offered = 'E' + str(new_val + 1).zfill(3)
            cursor.execute("""
                INSERT INTO Ejemplar (idEjemplar, idLibro, idEdicion, caratula, estado)
                VALUES (:new_exemplar, :book_ofrecibido, :edition_ofrecibido, empty_blob(), 'posesion')
            """, {"new_exemplar": new_exemplar_offered, 
                  "book_ofrecibido": book_ofrecibido, 
                  "edition_ofrecibido": edition_ofrecibido})
            

            cursor.execute("""
                SELECT NVL(MAX(TO_NUMBER(REGEXP_REPLACE(idIntercambio, '[^0-9]', ''))), 0)
                FROM Intercambio
            """)
            exchange_id = 'X' + str(cursor.fetchone()[0] + 1).zfill(3)
            

            if tipo_intercambio == "temporal":

                cursor.execute("""
                    INSERT INTO Intercambio (idIntercambio, tipoIntercambio, fechaInicio, fechaFin, estado)
                    VALUES (:exchange_id, :tipo, SYSDATE, :fecha_fin, :estado)
                """, {"exchange_id": exchange_id,
                      "tipo": tipo_intercambio,
                      "fecha_fin": fecha_fin_input,
                      "estado": "activo"})
            else:

                cursor.execute("""
                    INSERT INTO Intercambio (idIntercambio, tipoIntercambio, fechaInicio, fechaFin, estado)
                    VALUES (:exchange_id, :tipo, SYSDATE, NULL, :estado)
                """, {"exchange_id": exchange_id,
                      "tipo": tipo_intercambio,
                      "estado": "finalizado"})
            

            cursor.execute("""
                INSERT INTO LibroIntercambio (idIntercambio, idEjemplarOfrecido, idEjemplarRecibido, idUsuario)
                VALUES (:exchange_id, :offered, :received, :user_id)
            """, {"exchange_id": exchange_id, 
                  "offered": new_exemplar_offered, 
                  "received": exemplar_recibido, 
                  "user_id": user_id})
            

            cursor.execute("""
                SELECT NVL(MAX(TO_NUMBER(REGEXP_REPLACE(idInventario, '[^0-9]', ''))), 0)
                FROM Inventario
            """)
            inv_val = cursor.fetchone()[0]
            new_inventario = 'I' + str(inv_val + 1).zfill(3)
            cursor.execute("""
                INSERT INTO Inventario (idInventario, idEjemplar, fechaIngreso, motivo, idUsuarioOrigen)
                VALUES (:new_inventario, :exemplar, SYSDATE, 'intercambio', :user_id)
            """, {"new_inventario": new_inventario, 
                  "exemplar": new_exemplar_offered, 
                  "user_id": user_id})
            

            if tipo_intercambio == "temporal":
                nuevo_estado = "prestado"
            else:
                nuevo_estado = "no_posesion"
            cursor.execute("""
                UPDATE Ejemplar
                SET estado = :nuevo_estado
                WHERE idEjemplar = :exemplar
            """, {"nuevo_estado": nuevo_estado, "exemplar": exemplar_recibido})
            
            connection.commit()
            st.success("Intercambio realizado exitosamente. Código de intercambio: " + exchange_id)
        except Exception as ex:
            connection.rollback()
            st.error(f"Error al realizar intercambio: {ex}")
        finally:
            cursor.close()

def consultar_tabla(connection):
    st.header("Consultar Tabla")

    tablas = ["Usuario", "Libro", "Edicion", "Ejemplar", "Autor",
              "LibroAutor", "Genero", "LibroGenero", "Categoria",
              "LibroCategoria", "Donacion", "DonacionEjemplar", "Intercambio",
              "LibroIntercambio", "HistorialLectura", "Inventario", "ClasificacionLibro",
              "ValoracionLibro"]
    tabla_seleccionada = st.selectbox("Seleccione la tabla para consultar", tablas)
    
    if st.button("Consultar"):
        try:
            cursor = connection.cursor()
            query = f"SELECT * FROM {tabla_seleccionada}"
            cursor.execute(query)
            registros = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            

            if tabla_seleccionada.upper() == "EJEMPLAR":
                if "CARATULA" in col_names:
                    idx = col_names.index("CARATULA")
                    col_names.pop(idx)
                    registros = [tuple(item for i, item in enumerate(row) if i != idx) for row in registros]
            
            if registros:
                st.success(f"Registros de la tabla {tabla_seleccionada}:")
                df = pd.DataFrame(registros, columns=col_names)
                st.table(df)
            else:
                st.info(f"No se encontraron registros en la tabla {tabla_seleccionada}.")
        except Exception as ex:
            st.error(f"Error al consultar la tabla {tabla_seleccionada}: {ex}")
        finally:
            cursor.close()
def galeria_libros_disponibles(connection):

    st.header("Galería de Libros Disponibles")
    try:
        cursor = connection.cursor()
        query = """
            SELECT L.idLibro, L.titulo, E.idEjemplar, E.caratula
            FROM Libro L
            JOIN Ejemplar E ON L.idLibro = E.idLibro
            WHERE E.estado = 'posesion'
        """
        cursor.execute(query)
        registros = cursor.fetchall()
        
        if not registros:
            st.info("No hay libros disponibles.")
            return
        

            


        num_cols = 3
        cols = st.columns(num_cols)
        seleccionado = False  

        fixed_size = (200, 300)
        for idx, (idLibro, titulo, idEjemplar, caratula_blob) in enumerate(registros):
            col = cols[idx % num_cols]
            caption = f"{titulo} ({idLibro} - {idEjemplar})"
            

            if caratula_blob is not None:
                try:
                    data = caratula_blob.read() if hasattr(caratula_blob, "read") else caratula_blob
                    image = Image.open(io.BytesIO(data))

                    image = image.resize(fixed_size)
                    col.image(image, caption=caption, use_column_width=False)
                except Exception as img_ex:
                    col.write(caption)
                    col.error(f"Error al cargar imagen: {img_ex}")
            else:
                col.write(caption)
            

            if col.button("Seleccionar", key=f"select_{idEjemplar}"):
                st.session_state["selected_intercambio"] = {
                    "idEjemplarRecibido": idEjemplar
                }
                st.success(f"Se seleccionó: {caption}")
                seleccionado = True

            if (idx + 1) % num_cols == 0:
                cols = st.columns(num_cols)
        
        if seleccionado:
            st.info("Ahora dirígete a 'Intercambiar Libro' para continuar con el intercambio.")
        
        connection.commit() 
    except Exception as ex:
        st.error(f"Error al mostrar libros disponibles: {ex}")
    finally:
        cursor.close()



def subir_imagen_ejemplar(connection):
    st.header("Subir Imagen para Ejemplar")
    id_ejemplar = st.text_input("ID del Ejemplar")
    file = st.file_uploader("Sube la imagen (carátula)", type=["png", "jpg", "jpeg"])
    
    if st.button("Subir Imagen"):
        if not id_ejemplar.strip() or file is None:
            st.error("Proporcione el ID del ejemplar y seleccione una imagen.")
            return
        try:
            data = file.read()  
            cursor = connection.cursor()
            query = "UPDATE Ejemplar SET caratula = :img WHERE idEjemplar = :id"
            cursor.execute(query, {"img": data, "id": id_ejemplar})
            connection.commit()
            st.success("Imagen subida correctamente.")
        except Exception as ex:
            connection.rollback()
            st.error(f"Error al subir la imagen: {ex}")
        finally:
            cursor.close()
def informacion_usuario(connection):
    st.header("Información del Usuario")
    

    if st.session_state.get("role") == "user":
        user_id = st.session_state.user_id
    else:
        user_id = st.text_input("Ingrese el ID de Usuario para mostrar la información")
    
    if not user_id:
        st.error("Debe proporcionar un ID de Usuario.")
        return

    try:
        cursor = connection.cursor()
        query = """
            SELECT idUsuario, primerNombre, segundoNombre, primerApellido, segundoApellido,
                   foto, tipo, estado, telefono, email, ciudad, calle, carrera, numero
            FROM Usuario
            WHERE idUsuario = :u_id
        """
        cursor.execute(query, {"u_id": int(user_id)})
        row = cursor.fetchone()
        
        if row:

            st.markdown("### Foto de Perfil")
            foto = row[5]
            if foto is not None:
                try:
                    import io
                    from PIL import Image
                    image_data = foto.read() if hasattr(foto, "read") else foto
                    image = Image.open(io.BytesIO(image_data))
                    st.image(image, caption="Foto Actual del Usuario", width=150)
                except Exception as img_ex:
                    st.error(f"Error al mostrar la foto: {img_ex}")
            else:
                st.info("El usuario no tiene foto de perfil, se mostrará una imagen por defecto.")
                st.image("https://i.pinimg.com/236x/6c/55/d4/6c55d49dd6839b5b79e84a1aa6d2260d.jpg", caption="Foto por defecto", width=150)
            
            st.markdown("### Detalles del Usuario")
            st.write(f"**ID Usuario:** {row[0] or ''}")

            primerNombre = row[1] or ""
            segundoNombre = row[2] or ""
            primerApellido = row[3] or ""
            segundoApellido = row[4] or ""
            nombre_completo = f"{primerNombre} {segundoNombre} {primerApellido} {segundoApellido}".strip()
            st.write(f"**Nombre Completo:** {nombre_completo}")
            
            st.write(f"**Teléfono:** {row[8] or ''}")
            st.write(f"**Email:** {row[9] or ''}")
            st.write(f"**Ciudad:** {row[10] or ''}")

            if row[11] or row[12] or row[13]:
                calle = row[11] or ""
                carrera = row[12] or ""
                numero = row[13] or ""
                direccion = f"Calle {calle}, Carrera {carrera}, Número {numero}"
                st.write(f"**Dirección:** {direccion}")
            else:
                st.write("**Dirección:** ")
            
            st.write(f"**Estado:** {row[7] or ''}")
            if row[6] is not None:
                st.write(f"**Tipo de Usuario:** {'Admin' if row[6] else 'User'}")
            
            st.markdown("#### Actualizar Foto de Perfil")
            nuevo_archivo = st.file_uploader("Seleccione una nueva imagen (png, jpg, jpeg)", type=["png", "jpg", "jpeg"])
            if st.button("Actualizar Foto"):
                if nuevo_archivo is None:
                    st.error("Debe seleccionar una imagen para actualizar la foto de perfil.")
                else:
                    try:
                        new_data = nuevo_archivo.read()
                        cursor_update = connection.cursor()
                        update_query = "UPDATE Usuario SET foto = :img WHERE idUsuario = :u_id"
                        cursor_update.execute(update_query, {"img": new_data, "u_id": int(user_id)})
                        connection.commit()
                        st.success("Foto de perfil actualizada correctamente.")
                        from PIL import Image
                        import io
                        image = Image.open(io.BytesIO(new_data))
                        st.image(image, caption="Nueva Foto de Perfil", width=150)
                        cursor_update.close()
                    except Exception as upd_ex:
                        connection.rollback()
                        st.error(f"Error al actualizar la foto: {upd_ex}")
            
            st.markdown("---")
            st.markdown("### Estadísticas del Usuario")
            try:
                cursor2 = connection.cursor()
                cursor2.execute("SELECT COUNT(*) FROM Donacion WHERE idUsuarioDonador = :u_id", {"u_id": int(user_id)})
                don_count = cursor2.fetchone()[0]
                
                cursor2.execute("SELECT COUNT(*) FROM LibroIntercambio WHERE idUsuario = :u_id", {"u_id": int(user_id)})
                intercambios_count = cursor2.fetchone()[0]
                
                cursor2.execute("SELECT COUNT(*) FROM HistorialLectura WHERE idUsuario = :u_id", {"u_id": int(user_id)})
                lecturas_count = cursor2.fetchone()[0]
                cursor2.close()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Donaciones", don_count)
                col2.metric("Intercambios", intercambios_count)
                col3.metric("Lecturas", lecturas_count)
            except Exception as e:
                st.error(f"Error al obtener estadísticas: {e}")
        else:
            st.error("Usuario no encontrado.")
    except Exception as ex:
        st.error(f"Error al obtener información del usuario: {ex}")
    finally:
        cursor.close()

def intercambios_pendientes_usuario(connection):
    st.header("Intercambios Pendientes")
    

    if st.session_state.get("role") != "user":
        st.error("Esta opción solo está disponible para usuarios.")
        return
    
    user_id = st.session_state.user_id
    
    try:
        cursor = connection.cursor()
        query = """
            SELECT I.idIntercambio, I.fechaInicio, I.fechaFin
            FROM Intercambio I
            JOIN LibroIntercambio LI ON I.idIntercambio = LI.idIntercambio
            WHERE LI.idUsuario = :u_id
              AND I.estado = 'activo'
            ORDER BY I.fechaInicio DESC
        """
        cursor.execute(query, {"u_id": int(user_id)})
        rows = cursor.fetchall()
        
        if rows:
            st.success(f"Se encontraron {len(rows)} intercambios pendientes.")

            import pandas as pd
            df = pd.DataFrame(rows, columns=["ID Intercambio", "Fecha Inicio", "Fecha Fin"])

            df["Fecha Inicio"] = df["Fecha Inicio"].apply(lambda x: pd.to_datetime(x).strftime("%d/%m/%Y"))
            df["Fecha Fin"] = df["Fecha Fin"].apply(lambda x: pd.to_datetime(x).strftime("%d/%m/%Y") if x else "")
            st.table(df)
            
            st.markdown("### Resumen")
            col1, col2 = st.columns(2)
            col1.metric("Total Pendientes", len(rows))
        else:
            st.info("No tienes intercambios pendientes.")
    except Exception as ex:
        st.error(f"Error al obtener intercambios pendientes: {ex}")
    finally:
        cursor.close()