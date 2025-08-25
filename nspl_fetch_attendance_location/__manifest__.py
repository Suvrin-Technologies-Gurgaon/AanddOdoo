{
    'name': 'Fetch Attendance Location',
    'version': '18.0',
    'summary': 'Automatically fetch Check-In and Check-Out Locations in HR Attendance',
    'description': """
    This module enhances the HR Attendance system by automatically capturing 
    the geographic location (address) during Check-In and Check-Out:

    ✔ Fetches location data based on IP address and coordinates  
    ✔ Displays Check-In and Check-Out addresses in the attendance form  
    ✔ Seamless and automatic location capture when employees register attendance  

    Improve attendance tracking with geolocation visibility.
    """,
    'category': 'Human Resources/Attendances',
    'sequence': 10,
    'author': 'Namah Softech Private Limited',
    'maintainer': 'Namah Softech Private Limited',
    'company': 'Namah Softech Private Limited',
    'website': 'https://www.namahsoftech.com',
    'support': 'support@namahsoftech.com',
    'price': 19.99,
    'currency': 'USD',
    'contributors': ['Shivani Solanki'],
    'license': 'AGPL-3',
    'depends': ['hr_attendance'],
    'data': [
        'views/hr_attendance_view.xml',
    ],
    'images': ['static/description/img/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
