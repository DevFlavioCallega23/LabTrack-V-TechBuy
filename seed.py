from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    users_data = [
        {'username': 'Flavio', 'password': '250728', 'email': 'flavio@techbuy.com.br', 'role': 'master'},
        {'username': 'Erica', 'password': '123456', 'email': 'erica@techbuy.com.br', 'role': 'admin'},
        {'username': 'Roberto', 'password': '123456', 'email': 'roberto@techbuy.com.br', 'role': 'viewer'},
    ]

    created = 0
    for data in users_data:
        user = User.query.filter_by(username=data['username']).first()
        if not user:
            user = User(
                username=data['username'],
                email=data['email'],
                role=data['role']
            )
            user.set_password(data['password'])
            db.session.add(user)
            created += 1
            print(f'  Criado: {data["username"]} ({data["role"]})')
        else:
            print(f'  Existente: {data["username"]}')

    db.session.commit()
    print(f'\nSeed concluido! {created} usuario(s) criado(s).')
