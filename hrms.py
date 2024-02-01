from datetime import datetime

import pytz
from botocore.exceptions import NoCredentialsError
from flask import Blueprint, render_template, request, redirect, jsonify, session, flash
import mysql.connector
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import boto3

hrms = Blueprint("hrms", __name__, template_folder="hrms_templates")

hrm = mysql.connector.connect(
    user='Medisim',
    password='K60KSH2DOXQn8BGnM3SA',
    database='HRMS',
    host='medisim-testdb.cbmmrisq24o6.us-west-2.rds.amazonaws.com',
    port=3306,
    auth_plugin='mysql_native_password',
    autocommit=True,
)
cursor = hrm.cursor()


# If we want to test in Local
def user_time():
    current_time = datetime.now()
    formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
    return formatted_time


# Before deployment have to discomment this
# def user_time():
#     ist = pytz.timezone('Asia/Kolkata')  # IST time zone
#     utc_time = datetime.utcnow()
#     ist_time = utc_time.astimezone(ist)
#     formatted_time = ist_time.strftime('%Y-%m-%d %H:%M:%S')
#     return formatted_time


def get_user_ip():
    if 'X-Forwarded-For' in request.headers:
        # Use the first IP in the X-Forwarded-For header
        user_ip = request.headers['X-Forwarded-For'].split(',')[0].strip()
    else:
        # Use the default remote_addr
        user_ip = request.remote_addr
    return user_ip


@hrms.route('/hrms/home')
def hrms_home():
    emps_sql = "SELECT * FROM employee_profile WHERE lock_status=0"
    cursor.execute(emps_sql)
    emps = cursor.fetchall()
    emp_temp_sql = "SELECT * FROM employee_temp_table"
    cursor.execute(emp_temp_sql)
    emps_temps = cursor.fetchall()
    bg_sql = "SELECT blood_group FROM HRMS.blood_groups WHERE lock_status=0"
    cursor.execute(bg_sql)
    bg = cursor.fetchall()
    bgs = [bgs[0] for bgs in bg]
    dept_sql = "SELECT a.department_name FROM MTOP_MASTER.departments a WHERE a.lock_status = 0"
    cursor.execute(dept_sql)
    dept_names = cursor.fetchall()
    departments = [name[0] for name in dept_names]
    u_name = session.get('username')
    swch_rol_sql = "SELECT a.role_name, b.link FROM additional_roles_assigned a, MTOP_MASTER.roles b WHERE a.emp_name " \
                   "= %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (u_name,))
    swtch_roles = cursor.fetchall()
    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role='HR_Admin'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()
    return render_template("hrms_home.html", emps=emps, emps_temps=emps_temps, bgs=bgs, departments=departments,
                           swtch_roles=swtch_roles, menus=menus)


@hrms.route('/get_auths', methods=['POST'])
def get_auths():
    selectAuthority = request.form['selectAuthority']

    report_auth_sql = "SELECT reporting_authority_name FROM HRMS.reporting_authorities WHERE company_name= %s AND " \
                      "lock_status=0 "
    cursor.execute(report_auth_sql, (selectAuthority,))
    report_auth = cursor.fetchall()
    report_auths = [rprt[0] for rprt in report_auth]
    print(report_auths)
    # roles = get_roles_for_department(selected_department)  # Replace this function with your own data retrieval logic
    return jsonify({'report_auths': report_auths})


@hrms.route('/get_roles_options', methods=['POST'])
def get_roles_options():
    selected_department = request.form['selected_department']
    print(selected_department)
    cursor.execute("SELECT a.role FROM MTOP_MASTER.roles a WHERE a.department = %s", (selected_department,))
    roless = cursor.fetchall()
    roles = [role[0] for role in roless]
    print(roles)
    # roles = get_roles_for_department(selected_department)  # Replace this function with your own data retrieval logic
    return jsonify({'roles': roles})


@hrms.route('/hrms/recruit')
def employees():
    dept_sql = "SELECT a.department_name FROM MTOP_MASTER.departments a WHERE a.lock_status = 0"
    cursor.execute(dept_sql)
    dept_names = cursor.fetchall()
    departments = [name[0] for name in dept_names]
    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role='HR_Admin'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()
    return render_template("recruitment.html", departments=departments, menus=menus)


@hrms.route('/hrms/recruitment/doc_verification', methods=['POST'])
def doc_ver():
    global docss, onboard_id
    cursor = hrm.cursor()
    cursor.execute("SELECT prefix, start_id, current_id FROM id_generation where category_name='onboard' ")
    result = cursor.fetchone()
    if result:
        prefix, start_number, current_id = result
        onboard_id = f"{prefix}{current_id}"
        new_current_id = int(current_id) + 1
        new_current_id_str = f"{new_current_id:03d}"
        cursor.execute("UPDATE id_generation SET current_id = %s where category_name='onboard' ", (new_current_id_str,))
    if request.method == 'POST':
        session['i_name'] = request.form['i_name']
        i_name = session.get('i_name')
        email = request.form['email']
        session['company'] = request.form['company']
        company = session.get('company')
        session['joinee_category'] = request.form['emp_category']
        joinee_category = session.get('joinee_category')
        session['joinee_department'] = request.form['dept']
        joinee_department = session.get('joinee_department')
        session['joinee_role'] = request.form['roles']
        joinee_role = session.get('joinee_role')

        username = session.get('username')

        time = user_time()
        ip = get_user_ip()

        cursor = hrm.cursor()

        role_sql = """INSERT INTO onboard_details(onboard_id, joinee_name, email, company_name, joinee_category, 
        department, role, mail_sent_by, timestamp, ip_address) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
        role_val = (
            onboard_id, i_name, email, company, joinee_category, joinee_department, joinee_role, username, time, ip)
        cursor.execute(role_sql, role_val)
        hrm.commit()
        cursor.close()

        # SMTP Configuration
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587  # Example port, change it according to your SMTP server
        sender_email = 'msvr.it@gmail.com'
        password = 'xwoy gukd gtlb rezr'

        # Email content
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = email
        message['Subject'] = 'Onboard Process'
        # lOcal
        # body = f'Dear <b>{i_name}</b>, <br>' \
        #        f'\n\nYour Onboard Process for <b>{company}</b> for the role of <b>{joinee_role}</b> in the <b>{joinee_department}</b> department' \
        #        f'.\n\nDocuments needs to be upload and fill up your details in the below link carefully. <br>' \
        #        f'<b> Link:</b>  <a href="http://127.0.0.1:5000//hrms/recruitment/{i_name}/doc_process' \
        #        f'">http://127.0.0.1:5000/hrms/recruitment/{i_name}/doc_process</a> '
        # Live
        body = f'Dear <b>{i_name}</b>, <br>' \
               f'\n\nYour Onboard Process for <b>{company}</b> for the role of <b>{joinee_role}</b> in the <b>{joinee_department}</b> department' \
               f'.\n\nDocuments needs to be upload and fill up your details in the below link carefully. <br>' \
               f'<b> Link:</b>  <a href="http://prtlmed.us-west-2.elasticbeanstalk.com/hrms/recruitment/{i_name}/doc_process' \
               f'">http://prtlmed.us-west-2.elasticbeanstalk.com/hrms/recruitment/{i_name}/doc_process</a> '

        message.attach(MIMEText(body, 'html'))

        # Sending the email
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, email, message.as_string())
            print("Email sent successfully!")
        except Exception as e:
            print(f"Failed to send email. Error: {e}")

        flash("Mail Sent Successfully..!")

        return redirect('/hrms/recruit')


@hrms.route('/hrms/recruitment/<i_name>/doc_process')
def doc_process(i_name):
    global upload_edu_docs, upload_exp_docs

    onboasrd_sql = "SELECT * FROM onboard_details WHERE joinee_name =%s"
    cursor.execute(onboasrd_sql, (i_name,))
    onb_details = cursor.fetchall()
    joinee_category = [jn[5] for jn in onb_details]
    print(joinee_category)
    if joinee_category == ['Fresher']:
        upload_exp_sql = "SELECT doc_name FROM documents WHERE doc_for in ('Fresher') and lock_status=0"
        cursor.execute(upload_exp_sql)
        upload_exp_doc = cursor.fetchall()
        upload_exp_docs = [edu_docs[0] for edu_docs in upload_exp_doc]
    else:
        upload_exp_sql = "SELECT doc_name FROM documents WHERE doc_for in ('Experience') and lock_status=0"
        cursor.execute(upload_exp_sql)
        upload_exp_doc = cursor.fetchall()
        upload_exp_docs = [exp_docs[0] for exp_docs in upload_exp_doc]

    upload_com_sql = "SELECT doc_name FROM documents WHERE  doc_for ='Common' and lock_status=0"
    cursor.execute(upload_com_sql)
    upload_com_doc = cursor.fetchall()
    upload_com_docs = [com_docs[0] for com_docs in upload_com_doc]
    bg_sql = "SELECT blood_group FROM HRMS.blood_groups WHERE lock_status=0"
    cursor.execute(bg_sql)
    bg = cursor.fetchall()
    bgs = [bgs[0] for bgs in bg]

    return render_template('onboard.html', upload_exp_docs=upload_exp_docs,
                           upload_com_docs=upload_com_docs, onb_details=onb_details, bgs=bgs)


@hrms.route('/hrms/recruitment/onboarding', methods=['POST'])
def onboard():
    global file, file_url, temp_id
    cursor.execute("SELECT prefix, start_id, current_id FROM id_generation where category_name='temp_id' ")
    result = cursor.fetchone()
    if result:
        prefix, start_number, current_id = result
        temp_id = f"{prefix}{current_id}"
        new_current_id = int(current_id) + 1
        new_current_id_str = f"{new_current_id:03d}"
        cursor.execute("UPDATE id_generation SET current_id = %s where category_name='temp_id' ", (new_current_id_str,))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        workmail = request.form['workmail']
        dob = request.form['dob']
        blood = request.form['blood']
        company = request.form['company']
        alt_mobile = request.form['alt_mobile']
        dept = request.form['dept']
        role = request.form['role']
        emergencyPerson = request.form['emergencyPerson']
        emergencypersonContact = request.form['emergencypersonContact']
        marital_status = request.form['flexRadioDefault']
        gender = request.form['flexRadioDefault1']
        currentAddress = request.form['currentAddress']
        permanentAddress = request.form['permanentAddress']

        time = user_time()
        ip = get_user_ip()

        # S3 bucket details
        AWS_BUCKET_NAME = 'cmpnydocuments'
        AWS_FOLDER = 'onboard/'  # Base folder in your bucket
        s3 = boto3.client('s3', aws_access_key_id='AKIA6IY5WL6ZJ4ESQMUN',
                          aws_secret_access_key='qOZK8hUSyiF7j/VkmKULgATEgkeFTDaHzWZhTuuf')

        file_names = []
        # Upload files to S3
        for index, upload_com_docs in enumerate(request.files.getlist('12thDiplomaMark')):
            file_name = f"{name}/file_{index}_{upload_com_docs.filename}"
            try:
                s3.upload_fileobj(upload_com_docs, AWS_BUCKET_NAME, AWS_FOLDER + file_name)
                file_url = f"https://{AWS_BUCKET_NAME}.s3.amazonaws.com/{AWS_FOLDER}{file_name}"
                file_names.append((upload_com_docs.filename, file_url))
            except NoCredentialsError:
                print("Credentials not available")

            # for file_name, file_url in file_names:
        onb_sql = "INSERT INTO employee_temp_table (emp_temp_id, emp_name, emp_email, emp_mobile, alt_mob_number, " \
                  "emp_work_mail, company, department, role, emp_dob, emp_blood_group, emp_emergency_person_name, " \
                  "emp_emergency_person_contact_number, emp_gender, emp_marital_status, emp_current_address, " \
                  "emp_permanent_address, 10th_marksheet_name, 10th_marksheet_url, 12th_marksheet_name, " \
                  "12th_marksheet_url, degree_certificate_name, degree_certificate_url, aadhaar_name, " \
                  "aadhaar_name_url, offer_letter_name," \
                  "offer_letter_url, payslip_name, payslip_file_url, relieving_name, relieving_name_url, " \
                  " submitted_by, timestamp, ip_address) VALUES (%s, %s, %s, %s, " \
                  "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, " \
                  "%s, %s, %s, %s, %s, %s) "

        onb_val = (
            temp_id, name, email, mobile, alt_mobile, workmail, company, dept, role, dob, blood, emergencyPerson,
            emergencypersonContact, gender,
            marital_status,
            currentAddress, permanentAddress,
            file_names[0][0] if len(file_names) > 0 else None,
            file_names[0][1] if len(file_names) > 0 else None,
            file_names[1][0] if len(file_names) > 1 else None,
            file_names[1][1] if len(file_names) > 1 else None,
            file_names[2][0] if len(file_names) > 2 else None,
            file_names[2][1] if len(file_names) > 2 else None,
            file_names[3][0] if len(file_names) > 3 else None,
            file_names[3][1] if len(file_names) > 3 else None,
            file_names[4][0] if len(file_names) > 4 else None,
            file_names[4][1] if len(file_names) > 4 else None,
            file_names[5][0] if len(file_names) > 5 else None,
            file_names[5][1] if len(file_names) > 5 else None,
            file_names[6][0] if len(file_names) > 6 else None,
            file_names[6][1] if len(file_names) > 6 else None,
            name, time, ip)
        cursor.execute(onb_sql, onb_val)
        hrm.commit()
        flash("Details Submitted Successfully")
        return redirect('/hrms/recruitment/<i_name>/doc_process')


@hrms.route('/payslip')
def paysilp():
    e_name = session.get('getNameFromUser')

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    return render_template("pay_upload.html", e_name=e_name, menus=menus, swtch_roles=swtch_roles)


@hrms.route('/payslip/upload', methods=['POST'])
def payslip_upload():
    global values
    if request.method == 'POST':
        uploaded_file = request.files['file']

        name = session.get('username')

        time = user_time()
        ip = get_user_ip()

        for i, line in enumerate(uploaded_file):
            # Skip the first row (header)
            if i == 0:
                continue
            values = line.decode('utf-8').strip().split(',')

            payslip_query = "INSERT INTO payslip (emp_id, name, basic_salary, DA, gross_salary, TDS, PF, ESI, " \
                            "net_salary, " \
                            "month," \
                            "total_no_of_days, attended_days, total_leaves_taken, total_no_of_worked_hours, " \
                            "uploaded_by, " \
                            "timestamp, ip_address, lock_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, " \
                            "%s, " \
                            "%s, " \
                            "%s, %s, %s, %s, %s) "
            payslip_values = (
                values[0], values[1], values[2], values[3], values[4], values[5], values[6], values[7], values[8],
                values[9],
                values[10], values[11], values[12], values[13], name, time, ip, 0)
            cursor.execute(payslip_query, payslip_values)
        hrm.commit()
        flash("PaySlip Uploaded Successfully")
        return redirect("/payslip")


@hrms.route('/employee/attendance')
def emp_attendance():
    emp_att_sql = "SELECT name, date, min(attendance_timings), max(attendance_timings), TIMEDIFF(MAX(" \
                  "attendance_timings), MIN(attendance_timings)) FROM " \
                  "BIOMETRIC.face_attendance GROUP BY name, date"
    cursor.execute(emp_att_sql)
    emp_att = cursor.fetchall()

    return render_template("emp_attendance.html", emp_att=emp_att)


@hrms.route('/hrms/employee_add', methods=['POST'])
def employee_add():
    global emp_id
    if request.method == 'POST':
        company = request.form['company']
        if company == 'Highbrow Interactive':
            cursor.execute(
                "SELECT prefix, start_id, current_id FROM id_generation where category_name='highbrow_emp_id' ")
            result = cursor.fetchone()
            if result:
                prefix, start_number, current_id = result
                emp_id = f"{prefix}{current_id}"
                new_current_id = int(current_id) + 1
                new_current_id_str = f"{new_current_id:03d}"
                cursor.execute("UPDATE id_generation SET current_id = %s where category_name='highbrow_emp_id' ",
                               (new_current_id_str,))

        else:
            cursor.execute(
                "SELECT prefix, start_id, current_id FROM id_generation where category_name='medisim_emp_id' ")
            result = cursor.fetchone()
            if result:
                prefix, start_number, current_id = result
                emp_id = f"{prefix}{current_id}"
                new_current_id = int(current_id) + 1
                new_current_id_str = f"{new_current_id:03d}"
                cursor.execute("UPDATE id_generation SET current_id = %s where category_name='medisim_emp_id' ",
                               (new_current_id_str,))

        emp_name = request.form['emp_name']
        email = request.form['email']
        emp_mob_number = request.form['emp_mob_number']
        emp_alt_mob_number = request.form['emp_alt_mob_number']
        emp_work_email_id = request.form['emp_work_email_id']
        dob = request.form['dob']
        dob_datetime = datetime.strptime(dob, '%Y-%m-%d')
        formatted_dob = dob_datetime.strftime('%d:%m:%y')
        bg = request.form['bg']
        emergency_cntct_name = request.form['emergency_cntct_name']
        emergency_cntct_number = request.form['emergency_cntct_number']
        gender = request.form['gender']
        m_status = request.form['m_status']
        current_address = request.form['current_address']
        permanent_address = request.form['permanent_address']
        company = request.form['company']
        gross = request.form['gross']
        auths = request.form['auths']
        dept = request.form['dept']
        roles = request.form['roles']
        u_name = session.get('username')

        time = user_time()

        ip = get_user_ip()

        emp_add_query = "INSERT INTO employee_profile (emp_id, emp_name, emp_email, emp_mobile, emp_alt_mob, " \
                        "emp_work_mail, emp_dob, emp_blood_group, emp_emergency_contact_person_name, " \
                        "emp_emergency_contact_person_number, emp_gender, emp_marital_status, emp_current_address, " \
                        "emp_permanent_address, emp_cmpny_name, emp_gross_salary, emp_reporting_authority, " \
                        "emp_designation, emp_department, added_by, timestamp, ip_address, lock_status) VALUES (%s, " \
                        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        emp_add_val = (
            emp_id, emp_name, email, emp_mob_number, emp_alt_mob_number, emp_work_email_id, formatted_dob, bg,
            emergency_cntct_name, emergency_cntct_number, gender, m_status, current_address, permanent_address, company,
            gross, auths, roles, dept, u_name, time, ip, 0)
        cursor.execute(emp_add_query, emp_add_val)

        list_leave_types = ['Compensatory_Off', 'Sick_Leave', 'Privilage/Vacation', 'Wedding_Pre/Post']
        list_available_leaves = [0, 5, 12, 7]
        list_lock_status = [0, 0, 0, 1]

        for leave_type, available_leaves, leave_lock in zip(list_leave_types, list_available_leaves, list_lock_status):
            leave_bal_insert_sql = "INSERT INTO leave_balancing (emp_name, leave_type, total_leaves, booked_leaves, " \
                                   "available_leaves, lock_status, added_by, timestamp, ip_address) VALUES (%s, %s, " \
                                   "%s, %s, %s, %s, %s, %s) "
            leave_bal_insert_val = (
                emp_name, leave_type, available_leaves, 0, available_leaves, leave_lock, u_name, time,
                ip)
            cursor.execute(leave_bal_insert_sql, leave_bal_insert_val)
        hrm.commit()
        flash(f"Employee Added Successfully..! his/her emp_id is {emp_id}")
        return redirect('/hrms/home')


@hrms.route('/hrms/move_employee')
def move_emp():
    global with_month, authss
    move_emp_sql = "SELECT * FROM employee_temp_table"
    cursor.execute(move_emp_sql)
    move_emps = cursor.fetchall()
    dates = [dt[33].date() for dt in move_emps]
    date_strings = [str(date) for date in dates]
    dept_sql = "SELECT a.department_name FROM MTOP_MASTER.departments a WHERE a.lock_status = 0"
    cursor.execute(dept_sql)
    dept_names = cursor.fetchall()
    departments = [name[0] for name in dept_names]
    for date_strings in date_strings:
        print("")
    cmpny = [cmpy[7] for cmpy in move_emps]
    print(cmpny)
    if cmpny == ['Medisim Vr']:
        report_auths_sql = "SELECT reporting_authority_name FROM reporting_authorities WHERE company_name='Medisim " \
                           "Vr' AND lock_status=0 ORDER BY reporting_authority_name"
        cursor.execute(report_auths_sql)
        authsss = cursor.fetchall()
        authss = [auths[0] for auths in authsss]

    else:
        report_auths_sql = "SELECT reporting_authority_name FROM reporting_authorities WHERE company_name='Highbrow " \
                           "Interactive' AND lock_status=0 ORDER BY reporting_authority_name"
        cursor.execute(report_auths_sql)
        authsss = cursor.fetchall()
        authss = [auths[0] for auths in authsss]
    return render_template("move_employee.html", move_emps=move_emps, onboard_date=date_strings,
                           departments=departments, authss=authss)


@hrms.route('/get_employee_details', methods=['POST'])
def get_employee_details():
    employee_name = request.form.get('employee_name')
    print(employee_name)
    move_emp_sql_emp = "SELECT * FROM employee_temp_table WHERE emp_name LIKE %s"
    # cursor.execute(move_emp_sql_emp, (employee_name,))
    cursor.execute(move_emp_sql_emp, (f'%{employee_name}%',))
    onb_name = cursor.fetchall()
    print(onb_name)
    return jsonify({'onb_name': onb_name})


@hrms.route('/hrms/move_employee_add', methods=['POST'])
def move_employee_add():
    global emp_id
    if request.method == 'POST':
        company = request.form['company']
        if company == 'Highbrow Interactive':
            cursor.execute(
                "SELECT prefix, start_id, current_id FROM id_generation where category_name='highbrow_emp_id' ")
            result = cursor.fetchone()
            if result:
                prefix, start_number, current_id = result
                emp_id = f"{prefix}{current_id}"
                new_current_id = int(current_id) + 1
                new_current_id_str = f"{new_current_id:03d}"
                cursor.execute("UPDATE id_generation SET current_id = %s where category_name='highbrow_emp_id' ",
                               (new_current_id_str,))

        else:
            cursor.execute(
                "SELECT prefix, start_id, current_id FROM id_generation where category_name='medisim_emp_id' ")
            result = cursor.fetchone()
            if result:
                prefix, start_number, current_id = result
                emp_id = f"{prefix}{current_id}"
                new_current_id = int(current_id) + 1
                new_current_id_str = f"{new_current_id:03d}"
                cursor.execute("UPDATE id_generation SET current_id = %s where category_name='medisim_emp_id' ",
                               (new_current_id_str,))

        emp_name = request.form['emp_name']
        email = request.form['email']
        emp_mob_number = request.form['emp_mob_number']
        emp_alt_mob_number = request.form['emp_alt_mob_number']
        emp_work_email_id = request.form['emp_work_email_id']
        dob = request.form['dob']
        dob_datetime = datetime.strptime(dob, '%Y-%m-%d')
        formatted_dob = dob_datetime.strftime('%d:%m:%y')
        bg = request.form['bg']
        emergency_cntct_name = request.form['emergency_cntct_name']
        emergency_cntct_number = request.form['emergency_cntct_number']
        gender = request.form['gender']
        m_status = request.form['m_status']
        current_address = request.form['current_address']
        permanent_address = request.form['permanent_address']
        company = request.form['company']
        gross = request.form['gross']
        auths = request.form['auths']
        dept = request.form['dept']
        roles = request.form['roles']
        u_name = session.get('username')

        time = user_time()
        ip = get_user_ip()

        emp_add_query = "INSERT INTO employee_profile (emp_id, emp_name, emp_email, emp_mobile, emp_alt_mob, " \
                        "emp_work_mail, emp_dob, emp_blood_group, emp_emergency_contact_person_name, " \
                        "emp_emergency_contact_person_number, emp_gender, emp_marital_status, emp_current_address, " \
                        "emp_permanent_address, emp_cmpny_name, emp_gross_salary, emp_reporting_authority, " \
                        "emp_designation, emp_department, added_by, timestamp, ip_address, lock_status) VALUES (%s, " \
                        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        emp_add_val = (
            emp_id, emp_name, email, emp_mob_number, emp_alt_mob_number, emp_work_email_id, formatted_dob, bg,
            emergency_cntct_name, emergency_cntct_number, gender, m_status, current_address, permanent_address, company,
            gross, auths, roles, dept, u_name, time, ip, 0)
        cursor.execute(emp_add_query, emp_add_val)
        hrm.commit()

        list_leave_types = ['Compensatory_Off', 'Sick_Leave', 'Privilage/Vacation', 'Wedding_Pre/Post']
        list_available_leaves = [0, 5, 12, 7]
        list_lock_status = [0, 0, 0, 1]

        for leave_type, available_leaves, leave_lock in zip(list_leave_types, list_available_leaves, list_lock_status):
            leave_bal_insert_sql = "INSERT INTO leave_balancing (emp_name, leave_type, total_leaves, booked_leaves, " \
                                   "available_leaves, lock_status, added_by, timestamp, ip_address) VALUES (%s, %s, " \
                                   "%s, %s, %s, %s, %s, %s) "
            leave_bal_insert_val = (
                emp_name, leave_type, available_leaves, 0, available_leaves, leave_lock, u_name, time,
                ip)
            cursor.execute(leave_bal_insert_sql, leave_bal_insert_val)
        hrm.commit()

        status_update_sql = "UPDATE employee_temp_table SET emp_status=1 WHERE emp_name= %s"
        cursor.execute(status_update_sql, (emp_name,))
        hrm.commit()
        flash(f"Employee Moved Successfully..! his/her emp_id is {emp_id}")
        return redirect('/hrms/home')


@hrms.route('/hrms/additional_roles')
def additional_roles():
    add_roles_sql = "SELECT role FROM MTOP_MASTER.roles WHERE lock_status=0"
    cursor.execute(add_roles_sql)
    add_roless = cursor.fetchall()
    add_roles = [ar[0] for ar in add_roless]
    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role='HR_Admin'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()
    return render_template("additional_roles.html", add_roles=add_roles, menus=menus)


@hrms.route('/get_emps', methods=['POST'])
def get_emps():
    empName = request.form['empName']

    emps_sql = "SELECT emp_name FROM employee_profile WHERE emp_cmpny_name= %s AND " \
               "lock_status=0 "
    cursor.execute(emps_sql, (empName,))
    emps_name = cursor.fetchall()
    emp_namess = [emp[0] for emp in emps_name]
    return jsonify({'emp_namess': emp_namess})


@hrms.route('/employee_roles_add', methods=['POST'])
def employee_roles_add():
    if request.method == 'POST':
        empss = request.form['empss']
        add_roles = request.form['add_roles']
        username = session.get('username')

        time = user_time()
        ip = get_user_ip()

        add_role_insert_sql = "INSERT INTO additional_roles_assigned (emp_name, role_name, lock_status, assigned_by, timestamp, " \
                              "ip_address) VALUES (%s, %s, %s, %s, %s, %s) "
        add_role_insert_val = empss, add_roles, 0, username, time, ip
        cursor.execute(add_role_insert_sql, add_role_insert_val)
        hrm.commit()

        flash(f"Additional Role Assignd for {empss} ")
        return redirect('/hrms/additional_roles')


@hrms.route('/leave')
def leave():
    e_name = session.get('getNameFromUser')

    select_query = "select * from HRMS.leave_balancing where emp_name = %s AND lock_status = 0"
    cursor.execute(select_query, (e_name,))
    fetching_leave = cursor.fetchall()

    select_query_wed = "select * from HRMS.leave_balancing where emp_name = %s AND lock_status = 1"
    cursor.execute(select_query_wed, (e_name,))
    fetching_leave_new = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    return render_template('leave.html', fetching_leave=fetching_leave, e_name=e_name, swtch_roles=swtch_roles,
                           fetching_leave_new=fetching_leave_new, menus=menus)


@hrms.route('/leave/adding', methods=['POST'])
def adding():
    user_name = session.get('username')
    session['leave_type'] = request.form['leave_type']
    leave_type = session.get('leave_type')

    e_name = session.get('getNameFromUser')

    if request.method == 'POST':
        emp_id = request.form['emp_id']
        from_date_str = request.form['from_date']
        to_date_str = request.form['to_date']
        reason = request.form['reason']

        from_date = datetime.strptime(from_date_str, '%Y-%m-%d')
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d')
        now = datetime.utcnow()
        crnt_date = now.strftime('%Y-%m-%d %H:%M:%S')

        add = int(1)
        no_of_leaves = (to_date - from_date).days + add

        sql_query_insert = """INSERT INTO leaves(employee_id, leave_type, from_date, to_date, no_of_days, 
                               reason_for_leave, leave_status, applied_date) VALUES(%s, %s, %s, %s, %s, %s, %s, %s) """
        sql_val_insert = (emp_id, leave_type, from_date, to_date, no_of_leaves, reason, 0, crnt_date)
        cursor.execute(sql_query_insert, sql_val_insert)
        hrm.commit()

        flash("Applied Leave Successfully..!")
        return redirect('/leave')
    else:
        flash("Error: Leave type not found")

    return render_template('leave.html', u_name=user_name, e_name=e_name)


@hrms.route('/employee/get_leave_balance')
def get_leave_balance():
    e_name = session.get('getNameFromUser')
    leave_type = request.args.get('leave_type', '')

    try:
        with hrm.cursor() as cursor:
            print("Before execute")
            sql_query_available = "SELECT available_leaves FROM leave_balancing WHERE leave_type = %s AND emp_name = %s"
            avai_value = (leave_type, e_name)
            cursor.execute(sql_query_available, avai_value)
            result_available = cursor.fetchone()
            print("After execute: " + str(result_available))
            cursor.fetchall()

            if result_available:
                available_leaves = result_available[0]
                leaves = {
                    'available_leave': available_leaves
                }
                return jsonify(leaves)
            else:
                return jsonify({'error': 'Leave type not found'})

    except Exception as e:
        return jsonify({'error': str(e)})


@hrms.route('/team_lead')
def tl_home():
    e_name = session.get('getNameFromUser')

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Team_Lead'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    leaveApprove = "select a.emp_name, b.leave_type, b.from_date, b.to_date, b.no_of_days, b.reason_for_leave, " \
                   "b.leave_status, b.applied_date from HRMS.employee_profile a, HRMS.leaves b WHERE a.emp_name = " \
                   "b.employee_id and a.emp_reporting_authority = %s"
    cursor.execute(leaveApprove, (e_name,))
    finalLeaveApprove = cursor.fetchall()

    return render_template("tl_home.html", swtch_roles=swtch_roles, menus=menus, finalLeaveApprove=finalLeaveApprove,
                           e_name=e_name)


@hrms.route('/team_lead/leave_approval')
def tl_leave():
    e_name = session.get('getNameFromUser')

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Team_Lead'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    leaveApprove = "select b.id, a.emp_name, b.leave_type, b.from_date, b.to_date, b.no_of_days, b.reason_for_leave, " \
                   "b.leave_status, b.applied_date from HRMS.employee_profile a, HRMS.leaves b WHERE a.emp_name = " \
                   "b.employee_id and a.emp_reporting_authority = %s and b.leave_status=0"
    cursor.execute(leaveApprove, (e_name,))
    finalLeaveApprove = cursor.fetchall()
    session['EmpName'] = [fl[1] for fl in finalLeaveApprove]
    emp_name_lve = session.get('EmpName')
    print(emp_name_lve)

    return render_template("tl_home.html", swtch_roles=swtch_roles, menus=menus, finalLeaveApprove=finalLeaveApprove,
                           e_name=e_name)


@hrms.route('/approve_leave', methods=['POST'])
def approve_leave():
    global lc_cnt
    e_name = session.get('getNameFromUser')
    emp_name_lve = session.get('EmpName')

    print("After Approval " + str(emp_name_lve[0]))
    leave_type = request.form.get('leave_type')
    leave_id = request.form.get('leave_id')
    print("leave Type " + str(leave_type))

    update_query = "UPDATE HRMS.leaves SET leave_status = 1 WHERE id = %s"
    cursor.execute(update_query, (leave_id,))
    hrm.commit()
    if cursor.rowcount > 0:
        print("IN Cursor.rowcont" + str(leave_id))
        leave_update_sql = "SELECT no_of_days as leave_count, leave_type FROM leaves WHERE employee_id = %s AND " \
                           "id= %s AND leave_type = %s AND leave_status=1 "
        inserted_values = (emp_name_lve[0], leave_id, leave_type)
        cursor.execute(leave_update_sql, inserted_values)
        leaves_status = cursor.fetchall()
        for lc_cnt in leaves_status:
            leave_count = lc_cnt[0]
            leave_type = lc_cnt[1]
            update_query = "UPDATE HRMS.leave_balancing SET booked_leaves = booked_leaves + %s, available_leaves = " \
                           "available_leaves - %s WHERE emp_name = %s AND leave_type = %s "
            update_values = (leave_count, leave_count, emp_name_lve[0], leave_type)
            cursor.execute(update_query, update_values)
    else:
        print("Query Not Working")
    flash("Leave successfully approved", "success")
    print("Flash message approve successfully")
    return redirect('/team_lead/leave_approval')


@hrms.route('/reject_leave', methods=['POST'])
def reject_leave():
    leave_id = request.form.get('leave_id')

    update_query = "UPDATE HRMS.leaves SET leave_status = 2 WHERE id = %s"

    cursor.execute(update_query, (leave_id,))
    hrm.commit()

    flash("Leave rejected", "danger")
    print("Flash message reject successfully")
    return redirect('/team_lead/leave_approval')


@hrms.route('/calendar')
def cal():
    e_name = session.get('getNameFromUser')

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    cal_event_sql = "SELECT * FROM events ORDER BY id"
    cursor.execute(cal_event_sql)
    calendar = cursor.fetchall()
    return render_template('calendar.html', calendar=calendar, swtch_roles=swtch_roles, e_name=e_name, menus=menus)


@hrms.route("/insert", methods=["POST", "GET"])
def insert():
    if request.method == 'POST':
        title = request.form['title']
        start = request.form['start']
        end = request.form['end']
        print(title)
        print(start)
        cursor.execute("INSERT INTO events (title,start_event,end_event) VALUES (%s,%s,%s)", [title, start, end])
        hrm.commit()
        msg = 'success'
        return jsonify(msg)
    return redirect('/calendar')


@hrms.route("/update", methods=["POST", "GET"])
def update():
    if request.method == 'POST':
        title = request.form['title']
        start = request.form['start']
        end = request.form['end']
        id = request.form['id']
        print(title)
        print(start)
        cursor.execute("UPDATE events SET title = %s, start_event = %s, end_event = %s WHERE id = %s ",
                       [title, start, end, id])
        hrm.commit()

        msg = 'success'
        return jsonify(msg)
    return redirect('/calendar')


@hrms.route("/ajax_delete", methods=["POST", "GET"])
def ajax_delete():
    if request.method == 'POST':
        getid = request.form['id']
        print(getid)
        cursor.execute('DELETE FROM events WHERE id = {0}'.format(getid))
        hrm.commit()

        msg = 'Record deleted successfully'
        return jsonify(msg)
    return redirect('/calendar')


@hrms.route('/team')
def team():
    e_name = session.get('getNameFromUser')

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    team_members_query = "SELECT * FROM employee_profile WHERE emp_department in (select emp_department " \
                         "from employee_profile WHERE emp_name like %s) "
    cursor.execute(team_members_query, (f'%{e_name}%',))
    members = cursor.fetchall()
    dept = [dpmt[19] for dpmt in members]
    return render_template('team.html', members=members, dept=dept, e_name=e_name, menus=menus, swtch_roles=swtch_roles)


@hrms.route('/leave_application')
def leave_application():
    e_name = session.get('getNameFromUser')

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    sql_query = "select * from leaves where employee_id = %s"
    cursor.execute(sql_query, (e_name,))
    fet = cursor.fetchall()
    return render_template("leave_application.html", e_name=e_name, fet=fet, menus=menus, swtch_roles=swtch_roles)


@hrms.route('/hrms/leave_applications')
def hrLeavApplication():
    e_name = session.get('getNameFromUser')

    sql_query = "select * from leaves"
    cursor.execute(sql_query)
    fetch_data = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'HR_Admin'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    return render_template('HR_leave_application.html', fetch_data=fetch_data, e_name=e_name, menus=menus,
                           swtch_roles=swtch_roles)


@hrms.route('/HR_approve_leave/<int:id>', methods=['POST'])
def HR_approve_leave(id):
    update_query = "UPDATE leaves SET leave_status = 3 WHERE id = %s"
    cursor.execute(update_query, (id,))
    hrm.commit()
    # Add any additional logic or error handling as needed
    flash('Approved')
    return redirect('/hrms/leave_applications')


@hrms.route('/HR_reject_leave/<int:id>', methods=['POST'])
def HR_reject_leave(id):
    update_query = "UPDATE leaves SET leave_status = 4 WHERE id = %s"
    cursor.execute(update_query, (id,))
    hrm.commit()
    # Add any additional logic or error handling as needed
    flash('Rejected')
    return redirect('/hrms/leave_applications')


@hrms.route('/get_status')
def get_status():
    e_name = session.get('getNameFromUser')
    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    sql_query = "SELECT * FROM leaves WHERE employee_id = %s"
    cursor.execute(sql_query, (e_name,))
    leave_status = cursor.fetchall()
    return render_template("leave_status.html", e_name=e_name, leave_status=leave_status, menus=menus,
                           swtch_roles=swtch_roles)


@hrms.route('/delete_status', methods=['POST'])
def delete_status():
    e_name = session.get('getNameFromUser')
    leave_id = request.form.get('id')
    del_query = "DELETE FROM leaves WHERE id = %s AND employee_id = %s"
    cursor.execute(del_query, (leave_id, e_name))
    hrm.commit()
    flash("Leave Cancelled Successfully...!")
    return redirect("/get_status")


@hrms.route('/wedding_request_form', methods=['POST'])
def wedding_request_form():
    if request.method == 'POST':
        emp_name = request.form.get('emp_name')
        reason = request.form.get('reason')
        u_name = session.get('username')
        date_of_req = user_time()
        ip = get_user_ip()

        insert_query = "INSERT INTO weddingLeave_Request(employee_name, reason, lock_status, requested_by, " \
                       "requested_date, requested_ip) VALUES(%s, %s, %s, %s, %s, %s) "
        insert_values = (emp_name, reason, 0, u_name, date_of_req, ip)
        cursor.execute(insert_query, insert_values)
        hrm.commit()
        flash("Requested successfully..!")
        return redirect('/leave')


@hrms.route('/hrms/wedding_leave_request')
def view_weddingLeaveRequest():
    e_name = session.get('getNameFromUser')
    select_query = "SELECT * FROM weddingLeave_Request"
    cursor.execute(select_query)
    leaveRequest = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'HR_Admin'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    return render_template('HR_WeddingLeaveRequest.html', leaveRequest=leaveRequest, menus=menus, e_name=e_name,
                           swtch_roles=swtch_roles)


@hrms.route('/approve_leave_request/<name>', methods=['POST'])
def approve_leave_request(name):
    e_name = session.get('getNameFromUser')
    # Update weddingLeave_Request table
    update_wedding_query = "UPDATE weddingLeave_Request SET lock_status = 1 WHERE employee_name = %s"
    cursor.execute(update_wedding_query, (name,))

    # Update leave_balancing table
    update_leave_query = "UPDATE leave_balancing SET lock_status = 0 WHERE emp_name= %s AND " \
                         "leave_type='Wedding_Pre/Post' "
    cursor.execute(update_leave_query, (e_name,))
    # Commit changes to the database
    hrm.commit()
    flash('Wedding Leave Unlocked for the Employee')
    return redirect('/hrms/wedding_leave_request')


@hrms.route('/reject_leave_request/<name>', methods=['POST'])
def reject_leave_request(name):
    update_query = "UPDATE weddingLeave_Request SET lock_status = 2 WHERE employee_name = %s"
    cursor.execute(update_query, (name,))
    hrm.commit()
    # Add any additional logic or error handling as needed
    flash('Rejected')
    return redirect('/view_weddingLeaveRequest')


@hrms.route('/leave_policy')
def leave_policy():
    e_name = session.get('getNameFromUser')

    leave_policy_sql = "SELECT * FROM leave_policies WHERE lock_status=0"
    cursor.execute(leave_policy_sql)
    policies = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    return render_template("leave_policy.html", e_name=e_name, policies=policies, swtch_roles=swtch_roles, menus=menus)


@hrms.route('/hrms/leave_policy')
def leave_policy_hr():
    e_name = session.get('getNameFromUser')

    leave_policy_sql = "SELECT * FROM leave_policies WHERE lock_status=0"
    cursor.execute(leave_policy_sql)
    policies = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'HR_Admin'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    return render_template("hr_leave_policy.html", e_name=e_name, policies=policies, swtch_roles=swtch_roles,
                           menus=menus)


@hrms.route('/policy_making', methods=['POST'])
def policy_making():
    global policy_id
    cursor.execute("SELECT prefix, start_id, current_id FROM id_generation where category_name='policies' ")
    result = cursor.fetchone()
    if result:
        prefix, start_number, current_id = result
        policy_id = f"{prefix}{current_id}"
        new_current_id = int(current_id) + 1
        new_current_id_str = f"{new_current_id:03d}"
        cursor.execute("UPDATE id_generation SET current_id = %s where category_name='policies' ",
                       (new_current_id_str,))

    if request.method == 'POST':
        policy = request.form['policy']
        u_name = session.get("username")
        time = user_time()
        ip = get_user_ip()

        policy_insert_sql = "INSERT INTO leave_policies (policy_id, description, lock_status, created_by, " \
                            "created_timestamp, ip_address) VALUES (%s, %s, %s, %s, %s, %s) "
        policy_insert_val = (policy_id, policy, 0, u_name, time, ip)
        cursor.execute(policy_insert_sql, policy_insert_val)
        hrm.commit()
        flash("Policy Created Successfully..!")
    return redirect('/hrms/leave_policy')


@hrms.route('/work_from_home')
def work_from_home():
    e_name = session.get('getNameFromUser')

    wfh_sql = "SELECT * FROM work_from_home_request WHERE emp_name = %s"
    cursor.execute(wfh_sql, (e_name,))
    wfh = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Employee'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    return render_template("wfh.html", e_name=e_name, menus=menus, swtch_roles=swtch_roles, wfh=wfh)


@hrms.route('/wfh_request', methods=['post'])
def wfh_request():
    global wfh_id
    cursor.execute("SELECT prefix, start_id, current_id FROM id_generation where category_name='work_from_home' ")
    result = cursor.fetchone()
    if result:
        prefix, start_number, current_id = result
        wfh_id = f"{prefix}{current_id}"
        new_current_id = int(current_id) + 1
        new_current_id_str = f"{new_current_id:03d}"
        cursor.execute("UPDATE id_generation SET current_id = %s where category_name='work_from_home' ",
                       (new_current_id_str,))
    if request.method == 'POST':
        emp_name = request.form['emp_name']
        from_date_str = request.form['from_date']
        to_date_str = request.form['to_date']
        reason = request.form['reason']
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
        total_days = (to_date - from_date).days + 1

        u_name = session.get('username')
        time = user_time()
        ip = get_user_ip()

        wfh_request_sql = "INSERT INTO work_from_home_request (request_id, emp_name, from_date, to_date, total_days, " \
                          "reason, request_status, requested_by, requested_timestamp, request_person_ip) VALUES (" \
                          "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        wfh_request_val = (wfh_id, emp_name, from_date, to_date, total_days, reason, 0, u_name, time, ip)
        cursor.execute(wfh_request_sql, wfh_request_val)
        hrm.commit()
        flash("Work From Home Request Submitted Succesfully..!")
        return redirect('/work_from_home')


@hrms.route('/team_lead/work_from_home_approval')
def wfh_approval():
    e_name = session.get('getNameFromUser')

    wfh_sql = "SELECT * FROM work_from_home_request"
    cursor.execute(wfh_sql)
    wfh = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'Team_Lead'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()
    return render_template("wfh_approval.html", e_name=e_name, menus=menus, swtch_roles=swtch_roles, wfh=wfh)


@hrms.route('/wfh_request_approve/<id>', methods=['GET', 'POST'])
def approve_wfh_request(id):
    e_name = session.get('getNameFromUser')
    # Update weddingLeave_Request table
    update_wfh_query = "UPDATE work_from_home_request SET request_status = 1 WHERE request_id= %s "
    cursor.execute(update_wfh_query, (id,))
    # Commit changes to the database
    hrm.commit()
    flash('Work From Home Approved Successfully..!')
    return redirect('/team_lead/work_from_home_approval')


@hrms.route('/wfh_request_reject/<id>', methods=['GET', 'POST'])
def reject_wfh_request(id):
    update_reject_query = "UPDATE work_from_home_request SET request_status = 2 WHERE request_id= %s"
    cursor.execute(update_reject_query, (id,))
    hrm.commit()
    # Add any additional logic or error handling as needed
    flash('Work From Home Rejected Successfully..!')
    return redirect('/team_lead/work_from_home_approval')

@hrms.route('/hrms/work_from_home')
def hr_wfh_view():
    e_name = session.get('getNameFromUser')
    hr_wfh_sql = "select * from work_from_home_request"
    cursor.execute(hr_wfh_sql)
    hr_wfh = cursor.fetchall()

    swch_rol_sql = "SELECT a.role_name, b.link FROM HRMS.additional_roles_assigned a, MTOP_MASTER.roles b WHERE " \
                   "a.emp_name = %s AND a.role_name=b.role AND a.lock_status=0 "
    cursor.execute(swch_rol_sql, (e_name,))
    swtch_roles = cursor.fetchall()

    menu_sql = "SELECT menu_name, url FROM MTOP_MASTER.menu_master WHERE lock_status=0 AND role= 'HR_Admin'"
    cursor.execute(menu_sql)
    menus = cursor.fetchall()

    return render_template("hr_wfh_view.html", hr_wfh = hr_wfh, swtch_roles=swtch_roles, menus=menus, e_name=e_name)
