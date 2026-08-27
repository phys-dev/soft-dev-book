# Установка Arch Linux

## Введение

В этом руководстве мы рассмотрим процесс установки Arch Linux на виртуальной машине в VirtualBox. Сначала мы настроим виртуальную машину для использования Legacy BIOS, установим Arch Linux вручную, а затем переключимся на UEFI и настроим загрузчик для работы с UEFI.

## Создание виртуальной машины

1. Открой VirtualBox и создай новую виртуальную машину.
2. Введи имя виртуальной машины и выбери тип операционной системы **Linux** и версию **Arch Linux (64-bit)**.
3. Выдели необходимое количество оперативной памяти (рекомендуется не менее 2 ГБ).
4. Создай новый виртуальный жесткий диск и выбери формат VDI.
5. Выдели место на диске (рекомендуется не менее 20 ГБ).
6. В настройках виртуальной машины выбери **Legacy BIOS** (или **SeaBIOS**).
7. Выбери ISO образ Arch Linux.

## Установка Arch Linux с использованием Legacy BIOS

1. Запусти виртуальную машину и загрузись с ISO образа Arch Linux.

2. Используй `cfdisk` для разметки диска (`/dev/sda`). Создай следующие разделы:
   - `/dev/sda1`: 1G для EFI System Partition (ESP)
   - `/dev/sda2`: остальное пространство для корневой файловой системы

3. Создай файловую систему на ESP разделе:
   ```bash
   mkfs.fat -F32 /dev/sda1
   ```

4. Создай файловую систему на корневом разделе:
   ```bash
   mkfs.ext4 /dev/sda2
   ```

5. Смонтируй корневую файловую систему:
   ```bash
   mount /dev/sda2 /mnt
   ```

6. Создай и смонтируй ESP:
   ```bash
   mkdir /mnt/boot
   mount /dev/sda1 /mnt/boot
   ```

7. Установи базовую систему:
   ```bash
   pacstrap /mnt base linux linux-firmware
   ```

8. Сгенерируй файл fstab:
   ```bash
   genfstab -U /mnt >> /mnt/etc/fstab
   ```

9. Перейди в новую систему:
   ```bash
   arch-chroot /mnt
   ```

10. Установи загрузчик GRUB:
    ```bash
    pacman -S grub
    grub-install --target=i386-pc /dev/sda
    grub-mkconfig -o /boot/grub/grub.cfg
    ```

11. Установи пароль root:
    ```bash
    passwd
    ```

12. Выйди из chroot-окружения и размонтируй файловые системы:
    ```bash
    exit
    umount -R /mnt
    reboot
    ```

## Установка Arch Linux на RAID1

1. Запусти установочный образ Arch Linux.

2. Подготовь диски:
   ```bash
   cfdisk /dev/sda
   cfdisk /dev/sdb
   ```
   Создай разделы на обоих дисках (например, `/dev/sda1` и `/dev/sdb1`).

3. Создай RAID1 массив:
   ```bash
   mdadm --create --verbose /dev/md0 --level=1 --raid-devices=2 /dev/sda1 /dev/sdb1
   ```

4. Отформатируй RAID-массив:
   ```bash
   mkfs.ext4 /dev/md0
   ```

5. Смонтируй файловую систему:
   ```bash
   mount /dev/md0 /mnt
   ```

6. Установи базовую систему:
   ```bash
   pacstrap /mnt base linux linux-firmware mdadm
   ```

7. Сгенерируй fstab:
   ```bash
   genfstab -U /mnt >> /mnt/etc/fstab
   ```

8. Выполни chroot в новую систему:
   ```bash
   arch-chroot /mnt
   ```

9. Настрой mdadm:
   ```bash
   mdadm --detail --scan >> /etc/mdadm.conf
   ```

10. Настрой mkinitcpio:

    Откройте `/etc/mkinitcpio.conf` и добавьте `mdadm_udev` в HOOKS перед filesystems:
    ```bash
    HOOKS=(base udev autodetect modconf block mdadm_udev filesystems keyboard fsck)
    ```

11. Пересобери начальный RAM-диск:
    ```bash
    mkinitcpio -P
    ```

12. Установи GRUB:
    ```bash
    pacman -S grub
    ```

13. Установи GRUB на оба диска:
    ```bash
    grub-install --target=i386-pc /dev/sda
    grub-install --target=i386-pc /dev/sdb
    ```

14. Создай конфигурацию GRUB:
    ```bash
    grub-mkconfig -o /boot/grub/grub.cfg
    ```

15. Перезагрузи систему:
    ```bash
    exit
    umount -R /mnt
    reboot
    ```

После завершения установки, проверь, что система загружается с любого из дисков, отключая поочередно каждый из них.

## Переключение на UEFI и настройка загрузчика

1. Останови виртуальную машину.
2. В настройках виртуальной машины измени BIOS на UEFI.
3. Запусти виртуальную машину и загрузись с ISO образа Arch Linux.

4. Смонтируй корневую файловую систему и ESP:
   ```bash
   mount /dev/sda2 /mnt
   mount /dev/sda1 /mnt/boot
   arch-chroot /mnt
   ```

5. Установи необходимые пакеты для загрузки с UEFI:
   ```bash
   pacman -S grub efibootmgr dosfstools os-prober mtools
   ```

6. Установи загрузчик GRUB с поддержкой UEFI:
   ```bash
   grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB
   grub-mkconfig -o /boot/grub/grub.cfg
   efibootmgr -v
   ```

Ты должны увидеть запись для GRUB в выводе команды `efibootmgr -v`.
