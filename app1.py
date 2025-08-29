import logging

logging.basicConfig(level=logging.DEBUG)

@app.route('/update_attendance', methods=['POST'])
def update_attendance():
    if 'user_id' not in session or session.get('user_type') != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized access'})

    teacher_id = session['user_id']
    data = request.form.to_dict()
    student_id = request.form.get('student_id')
    
    if not student_id:
        return jsonify({'success': False, 'message': 'Student ID is required'})

    connection = get_db()
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM student WHERE user_id = %s", (student_id,))
        student_exists = cursor.fetchone()[0] > 0

        if not student_exists:
            return jsonify({'success': False, 'message': 'Student ID does not exist'})

        for key, value in data.items():
            if key.startswith('attended_'):
                subject_name = key.split('_')[1]
                logging.debug(f'Processing subject: {subject_name}')
                
                cursor.execute("SELECT subject_id FROM subject WHERE subject_name = %s", (subject_name,))
                subject_id = cursor.fetchone()

                if subject_id is None:
                    logging.debug(f'Subject {subject_name} does not exist')
                    return jsonify({'success': False, 'message': f'Subject {subject_name} does not exist'})
                
                subject_id = subject_id[0]
                logging.debug(f'Found subject_id: {subject_id}')
                
                attended_values = value.split(' ')
                conducted_key = f'conducted_{subject_id}'
                conducted_values = data.get(conducted_key, '').split(',')

                cursor.execute("SELECT COUNT(*) FROM teacher_subject WHERE teacher_id = %s AND subject_id = %s", (teacher_id, subject_id))
                authorized = cursor.fetchone()[0] > 0

                if not authorized:
                    logging.debug(f'Unauthorized to update attendance for subject {subject_id}')
                    return jsonify({'success': False, 'message': f'Unauthorized to update attendance for subject {subject_id}'})

                for attended, conducted in zip(attended_values, conducted_values):
                    attended = int(attended.strip())
                    conducted = int(conducted.strip())

                    cursor.execute("SELECT COUNT(*) FROM attendance1 WHERE student_id = %s AND subject_id = %s", (student_id, subject_id))
                    record_exists = cursor.fetchone()[0] > 0

                    if record_exists:
                        logging.debug(f'Updating attendance for student {student_id} and subject {subject_id}')
                        cursor.execute("""
                            UPDATE attendance1 
                            SET total_classes_attended = %s, total_classes_conducted = %s
                            WHERE student_id = %s AND subject_id = %s
                        """, (attended, conducted, student_id, subject_id))
                    else:
                        logging.debug(f'Inserting attendance for student {student_id} and subject {subject_id}')
                        cursor.execute("""
                            INSERT INTO attendance1 (student_id, subject_id, total_classes_attended, total_classes_conducted)
                            VALUES (%s, %s, %s, %s)
                        """, (student_id, subject_id, attended, conducted))

        connection.commit()
        return jsonify({'success': True, 'message': 'Attendance updated successfully'})
    except Exception as e:
        connection.rollback()
        logging.error(f'Error: {e}')
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
