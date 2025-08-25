{
    'name': 'Fetch Attendance Location',
    'version': '18.0.1.1',
    'license': 'LGPL-3',
    'category': 'Human Resources/Attendances',
    'summary': 'HR attendance automatic check-in address and checkout address in attendance form view',
    'description': """This module will help you to get attendance check-in and checkout address through the IP address and coordinates. It fetches attendance location automatically when the user checks in and checks out.""",
    'author': 'Akshat Gupta',
    'website': 'https://github.com/Akshat-10',
    'support': 'akshat.gupta10m@gmail.com',
    'depends': ['hr_attendance'],
    'data': [
        'views/hr_attendance_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/banner.gif'],
}
