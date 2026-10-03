import database


class UserService:
    def get_user(self):
        db = database.Database()

        db.get_user()


class User:
    pass


class Admin(User):
    pass
