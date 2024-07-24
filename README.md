# LearnBetter

[SVG Diagram: Magpie Learning Platform Architecture]

1. Main Application (app.py)
   |
   +-- Student Routes (/student)
   |   |
   |   +-- Home (/)
   |   +-- Login (/login)
   |   +-- Register (/register)
   |   +-- My Courses (/my_courses)
   |   +-- Course Details (/course/<course_id>)
   |   +-- Dashboard (/dashboard)
   |   +-- Profile (/profile)
   |   +-- Logout (/logout)
   |   +-- Forgot Password (/forgot_password)
   |   +-- Purchase Course (/purchase_course/<course_id>)
   |
   +-- Teacher Routes (/teacher)
       |
       +-- Login (/login)
       +-- Register (/register)
       +-- Profile (/profile)
       +-- Dashboard (/dashboard)
       +-- Add Course (/add_course)
       +-- Edit Course (/edit_course/<course_id>)
       +-- View Course (/view_course/<course_id>)
       +-- Add Video (/add_video/<course_id>)

2. Firebase Structure
   |
   +-- Firestore Database
   |   |
   |   +-- student_details
   |   |   +-- [user_id]
   |   |       +-- purchased_courses
   |   |       +-- progress
   |   |
   |   +-- teacher_details
   |   |   +-- [user_id]
   |   |       +-- name
   |   |       +-- email
   |   |       +-- about
   |   |       +-- educational_experience
   |   |       +-- specialization
   |   |       +-- teaching_experience
   |   |       +-- website
   |   |
   |   +-- course_details
   |   |   +-- [course_id]
   |   |       +-- course_name
   |   |       +-- course_duration
   |   |       +-- course_price
   |   |       +-- course_instructor
   |   |       +-- course_instructor_id
   |   |       +-- total_enrollments
   |   |       +-- total_revenue
   |   |       +-- average_rating
   |   |       +-- total_ratings
   |   |       +-- videos
   |   |       +-- enrollments
   |   |       +-- ratings
   |   |
   |   +-- users
   |       +-- [user_id]
   |           +-- username
   |           +-- email
   |           +-- role
   |           +-- courses (for teachers)
   |
   +-- Realtime Database
       |
       +-- users
           +-- [user_id]
               +-- username
               +-- email
               +-- password
               +-- role

3. Data Flow Arrows
   - Student routes <--> Firestore (student_details, course_details)
   - Teacher routes <--> Firestore (teacher_details, course_details)
   - Authentication <--> Realtime Database (users)
   - File uploads <--> Google Drive API

4. External Services
   - Google Drive API (for video storage)
   - Email Service (for forgot password functionality)
