import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() => runApp(const PosApp());
const gold = Color(0xffe5b820),
    dark = Color(0xff101119),
    panel = Color(0xff1a1c27),
    card = Color(0xff252836);

class Product {
  const Product(this.category, this.name, this.price, this.icon);
  final String category, name, icon;
  final double price;
}

class Line {
  Line(this.product, [this.qty = 1]);
  final Product product;
  int qty;
}

class Order {
  Order(this.id, this.place, this.type, this.lines, this.time);
  final String id, place, type;
  final List<Line> lines;
  final DateTime time;
  String status = 'Pendiente';
  double get total => lines.fold(0, (s, l) => s + l.product.price * l.qty);
  Map<String, dynamic> toJson() => {
    'id': id,
    'place': place,
    'type': type,
    'time': time.toIso8601String(),
    'status': status,
    'lines': lines
        .map(
          (l) => {
            'name': l.product.name,
            'category': l.product.category,
            'price': l.product.price,
            'icon': l.product.icon,
            'qty': l.qty,
          },
        )
        .toList(),
  };
  static Order fromJson(Map<String, dynamic> json) {
    final lines = (json['lines'] as List).map((item) {
      final data = item as Map<String, dynamic>;
      final product = Product(
        (data['category'] as String?) ?? 'Otros',
        data['name'] as String,
        (data['price'] as num?)?.toDouble() ?? 0,
        (data['icon'] as String?) ?? '•',
      );
      return Line(product, data['qty'] as int);
    }).toList();
    return Order(
      json['id'] as String,
      json['place'] as String,
      json['type'] as String,
      lines,
      DateTime.parse(json['time'] as String),
    )..status = ((json['status'] as String?) ?? 'Pendiente');
  }
}

const defaultProducts = <Product>[
  Product('Tacos', 'Taco de pastor', 22, '🌮'),
  Product('Tacos', 'Taco de bistec', 25, '🌮'),
  Product('Tacos', 'Taco de suadero', 25, '🌮'),
  Product('Especiales', 'Gringa', 65, '🫓'),
  Product('Especiales', 'Quesadilla', 45, '🧀'),
  Product('Especiales', 'Alambre', 120, '🍳'),
  Product('Bebidas', 'Agua fresca', 30, '🥤'),
  Product('Bebidas', 'Refresco', 35, '🥤'),
  Product('Extras', 'Cebollitas', 40, '🧅'),
  Product('Extras', 'Guacamole', 45, '🥑'),
];

class PosApp extends StatelessWidget {
  const PosApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'Punto de Venta Express',
    theme: ThemeData.dark(useMaterial3: true).copyWith(
      scaffoldBackgroundColor: dark,
      colorScheme: const ColorScheme.dark(
        primary: gold,
        secondary: gold,
        surface: panel,
      ),
    ),
    home: const PosHome(),
  );
}

class PosHome extends StatefulWidget {
  const PosHome({super.key});
  @override
  State<PosHome> createState() => _PosHomeState();
}

class _PosHomeState extends State<PosHome> {
  int page = 0;
  String category = 'Todos', type = 'Mostrador', search = '';
  final reference = TextEditingController();
  final businessController = TextEditingController();
  final cart = <Line>[], orders = <Order>[], sales = <Order>[];
  final productList = <Product>[...defaultProducts];
  String businessName = 'PUNTO DE VENTA';
  @override
  void initState() {
    super.initState();
    loadData();
  }

  Future<void> loadData() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final savedOrders = jsonDecode(prefs.getString('orders') ?? '[]') as List;
      final savedSales = jsonDecode(prefs.getString('sales') ?? '[]') as List;
      orders
        ..clear()
        ..addAll(
          savedOrders.map((e) => Order.fromJson(e as Map<String, dynamic>)),
        );
      sales
        ..clear()
        ..addAll(
          savedSales.map((e) => Order.fromJson(e as Map<String, dynamic>)),
        );
      final rawProducts = prefs.getString('products');
      productList
        ..clear()
        ..addAll(
          rawProducts == null
              ? defaultProducts
              : (jsonDecode(rawProducts) as List).map((e) {
                  final p = e as Map<String, dynamic>;
                  return Product(
                    p['category'] as String,
                    p['name'] as String,
                    (p['price'] as num).toDouble(),
                    p['icon'] as String,
                  );
                }),
        );
    } catch (_) {
      orders.clear();
      sales.clear();
      productList
        ..clear()
        ..addAll(defaultProducts);
    }
    businessName = prefs.getString('business_name') ?? 'PUNTO DE VENTA';
    businessController.text = businessName;
    if (mounted) setState(() {});
  }

  Future<void> saveData() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      'orders',
      jsonEncode(orders.map((o) => o.toJson()).toList()),
    );
    await prefs.setString(
      'sales',
      jsonEncode(sales.map((o) => o.toJson()).toList()),
    );
    await prefs.setString(
      'products',
      jsonEncode(
        productList
            .map(
              (p) => {
                'category': p.category,
                'name': p.name,
                'price': p.price,
                'icon': p.icon,
              },
            )
            .toList(),
      ),
    );
    await prefs.setString('business_name', businessName);
  }

  double get total => cart.fold(0, (s, l) => s + l.product.price * l.qty);
  int get count => cart.fold(0, (s, l) => s + l.qty);
  List<Product> get filtered => productList
      .where(
        (p) =>
            (category == 'Todos' || p.category == category) &&
            p.name.toLowerCase().contains(search.toLowerCase()),
      )
      .toList();
  void add(Product p) => setState(() {
    final i = cart.indexWhere((l) => l.product.name == p.name);
    i < 0 ? cart.add(Line(p)) : cart[i].qty++;
  });
  void quantity(Line l, int d) => setState(() {
    l.qty += d;
    if (l.qty < 1) cart.remove(l);
  });
  void toast(String text) => ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(text), behavior: SnackBarBehavior.floating),
  );
  void send() {
    if (cart.isEmpty) {
      toast('Agrega productos primero');
      return;
    }
    final now = DateTime.now();
    setState(() {
      orders.insert(
        0,
        Order(
          now.millisecondsSinceEpoch.toString().substring(9),
          reference.text.trim().isEmpty ? type : reference.text.trim(),
          type,
          cart.map((l) => Line(l.product, l.qty)).toList(),
          now,
        ),
      );
      cart.clear();
      reference.clear();
    });
    saveData();
    toast('Comanda enviada a cocina');
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 800;
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 66,
        backgroundColor: dark,
        shape: const Border(bottom: BorderSide(color: gold, width: 3)),
        title: Row(
          children: [
            CircleAvatar(
              backgroundColor: gold,
              child: Text(
                'PV',
                style: TextStyle(color: dark, fontWeight: FontWeight.w900),
              ),
            ),
            SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  businessName,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                Text('EXPRESS', style: TextStyle(fontSize: 11, color: gold)),
              ],
            ),
          ],
        ),
      ),
      body: IndexedStack(
        index: page,
        children: [
          wide
              ? Row(
                  children: [
                    Expanded(child: catalog()),
                    SizedBox(width: 370, child: orderPanel()),
                  ],
                )
              : catalog(),
          ordersPage(false),
          ordersPage(true),
          cutPage(),
          settingsPage(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: page,
        onDestinationSelected: (v) => setState(() => page = v),
        backgroundColor: panel,
        indicatorColor: gold,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.point_of_sale),
            label: 'Pedidos',
          ),
          NavigationDestination(
            icon: Icon(Icons.receipt_long),
            label: 'Cuentas',
          ),
          NavigationDestination(
            icon: Icon(Icons.soup_kitchen),
            label: 'Cocina',
          ),
          NavigationDestination(icon: Icon(Icons.assessment), label: 'Corte'),
          NavigationDestination(icon: Icon(Icons.settings), label: 'Negocio'),
        ],
      ),
      floatingActionButton: !wide && page == 0
          ? FloatingActionButton.extended(
              backgroundColor: gold,
              foregroundColor: dark,
              onPressed: () => showModalBottomSheet(
                context: context,
                isScrollControlled: true,
                backgroundColor: panel,
                builder: (_) => StatefulBuilder(
                  builder: (_, refresh) => SizedBox(
                    height: MediaQuery.sizeOf(context).height * .82,
                    child: orderPanel(refresh),
                  ),
                ),
              ),
              icon: const Icon(Icons.shopping_cart),
              label: Text('$count · \$${total.toStringAsFixed(2)}'),
            )
          : null,
    );
  }

  Widget catalog() => Padding(
    padding: const EdgeInsets.all(10),
    child: Column(
      children: [
        SizedBox(
          height: 44,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: ['Todos', 'Tacos', 'Especiales', 'Bebidas', 'Extras']
                .map(
                  (n) => Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: ChoiceChip(
                      selectedColor: gold,
                      labelStyle: TextStyle(
                        color: category == n ? dark : Colors.white,
                      ),
                      label: Text(n),
                      selected: category == n,
                      onSelected: (_) => setState(() => category = n),
                    ),
                  ),
                )
                .toList(),
          ),
        ),
        const SizedBox(height: 7),
        TextField(
          decoration: const InputDecoration(
            prefixIcon: Icon(Icons.search),
            hintText: 'Buscar producto…',
            filled: true,
            fillColor: panel,
            border: OutlineInputBorder(),
          ),
          onChanged: (v) => setState(() => search = v),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: LayoutBuilder(
            builder: (_, box) {
              final columns = box.maxWidth >= 900
                  ? 6
                  : box.maxWidth >= 600
                  ? 4
                  : 2;
              return GridView.builder(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: columns,
                  crossAxisSpacing: 7,
                  mainAxisSpacing: 7,
                  childAspectRatio: .93,
                ),
                itemCount: filtered.length,
                itemBuilder: (_, i) => productCard(filtered[i]),
              );
            },
          ),
        ),
      ],
    ),
  );
  Widget productCard(Product p) => InkWell(
    onTap: () => add(p),
    borderRadius: BorderRadius.circular(12),
    child: Ink(
      decoration: BoxDecoration(
        color: card,
        border: Border.all(color: const Color(0xff393d4e)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Center(
              child: Text(p.icon, style: const TextStyle(fontSize: 48)),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 2),
            child: Text(
              p.name,
              maxLines: 2,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 9),
            child: Text(
              '\$${p.price.toStringAsFixed(2)}',
              style: const TextStyle(color: gold, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    ),
  );
  Widget orderPanel([StateSetter? sheet]) {
    void refresh(VoidCallback work) {
      setState(work);
      sheet?.call(() {});
    }

    return Padding(
      padding: const EdgeInsets.all(13),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'PEDIDO ACTUAL',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 9),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'Mostrador', label: Text('Mostrador')),
              ButtonSegment(value: 'Para llevar', label: Text('Llevar')),
              ButtonSegment(value: 'Mesa', label: Text('Mesa')),
            ],
            selected: {type},
            onSelectionChanged: (v) => refresh(() => type = v.first),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: reference,
            decoration: const InputDecoration(
              hintText: 'Nombre, número o mesa',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: cart.isEmpty
                ? const Center(
                    child: Text(
                      'Toca un producto para comenzar',
                      style: TextStyle(color: Colors.white54),
                    ),
                  )
                : ListView(
                    children: cart
                        .map(
                          (l) => ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(l.product.name),
                            subtitle: Text(
                              '\$${(l.product.price * l.qty).toStringAsFixed(2)}',
                            ),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton.filledTonal(
                                  onPressed: () => quantity(l, -1),
                                  icon: const Icon(Icons.remove),
                                ),
                                Text(
                                  '${l.qty}',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                IconButton.filledTonal(
                                  onPressed: () => quantity(l, 1),
                                  icon: const Icon(Icons.add),
                                ),
                              ],
                            ),
                          ),
                        )
                        .toList(),
                  ),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'TOTAL',
                style: TextStyle(fontSize: 21, fontWeight: FontWeight.w900),
              ),
              Text(
                '\$${total.toStringAsFixed(2)}',
                style: const TextStyle(
                  fontSize: 24,
                  color: gold,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          FilledButton.icon(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xff3197d5),
              minimumSize: const Size.fromHeight(50),
            ),
            onPressed: send,
            icon: const Icon(Icons.print),
            label: const Text('ENVIAR COMANDA'),
          ),
          const SizedBox(height: 7),
          FilledButton.icon(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xff20ad63),
              minimumSize: const Size.fromHeight(50),
            ),
            onPressed: cart.isEmpty
                ? null
                : () {
                    final now = DateTime.now();
                    refresh(() {
                      sales.insert(
                        0,
                        Order(
                          now.millisecondsSinceEpoch.toString().substring(9),
                          reference.text.trim().isEmpty
                              ? type
                              : reference.text.trim(),
                          type,
                          cart.map((l) => Line(l.product, l.qty)).toList(),
                          now,
                        )..status = 'Pagado',
                      );
                      cart.clear();
                      reference.clear();
                    });
                    saveData();
                    toast('Cuenta cobrada');
                  },
            icon: const Icon(Icons.payments),
            label: const Text('COBRAR'),
          ),
        ],
      ),
    );
  }

  Widget ordersPage(bool kitchen) {
    final visible = orders
        .where((o) => kitchen ? o.status != 'Entregado' : o.status != 'Pagado')
        .toList();
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            kitchen ? 'COMANDAS DE COCINA' : 'CUENTAS ACTIVAS',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          Expanded(
            child: visible.isEmpty
                ? const Center(child: Text('No hay pedidos pendientes'))
                : ListView.builder(
                    itemCount: visible.length,
                    itemBuilder: (_, i) {
                      final o = visible[i];
                      return Card(
                        color: panel,
                        shape: RoundedRectangleBorder(
                          side: const BorderSide(color: gold),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${o.place} · #${o.id}',
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(
                                '${o.type} · ${o.time.hour.toString().padLeft(2, '0')}:${o.time.minute.toString().padLeft(2, '0')} · ${o.status}',
                                style: const TextStyle(color: Colors.white54),
                              ),
                              const Divider(),
                              ...o.lines.map(
                                (l) => Text('${l.qty}×  ${l.product.name}'),
                              ),
                              const SizedBox(height: 9),
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    '\$${o.total.toStringAsFixed(2)}',
                                    style: const TextStyle(
                                      fontSize: 20,
                                      color: gold,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  FilledButton(
                                    onPressed: () {
                                      setState(() {
                                        o.status = kitchen
                                            ? 'Entregado'
                                            : 'Pagado';
                                        if (!kitchen && !sales.contains(o)) {
                                          sales.insert(0, o);
                                        }
                                      });
                                      saveData();
                                    },
                                    child: Text(
                                      kitchen ? 'ENTREGADO' : 'COBRAR',
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget cutPage() {
    final now = DateTime.now();
    final today = sales
        .where(
          (o) =>
              o.time.year == now.year &&
              o.time.month == now.month &&
              o.time.day == now.day,
        )
        .toList();
    final amount = today.fold<double>(0, (sum, o) => sum + o.total);
    final average = today.isEmpty ? 0 : amount / today.length;
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        const Text(
          'CORTE DE CAJA',
          style: TextStyle(fontSize: 23, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 9,
          runSpacing: 9,
          children: [
            summaryCard(
              'VENTA DEL DÍA',
              '\$${amount.toStringAsFixed(2)}',
              Icons.payments,
            ),
            summaryCard('TICKETS', '${today.length}', Icons.receipt),
            summaryCard(
              'TICKET PROMEDIO',
              '\$${average.toStringAsFixed(2)}',
              Icons.analytics,
            ),
          ],
        ),
        const SizedBox(height: 15),
        const Text(
          'VENTAS COBRADAS',
          style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
        ),
        ...today.map(
          (o) => Card(
            color: panel,
            child: ListTile(
              title: Text('${o.place} · #${o.id}'),
              subtitle: Text(
                '${o.time.hour.toString().padLeft(2, '0')}:${o.time.minute.toString().padLeft(2, '0')} · ${o.type}',
              ),
              trailing: Text(
                '\$${o.total.toStringAsFixed(2)}',
                style: const TextStyle(
                  color: gold,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ),
        if (today.isEmpty)
          const Padding(
            padding: EdgeInsets.all(35),
            child: Center(child: Text('Aún no hay ventas cobradas hoy')),
          ),
      ],
    );
  }

  Widget summaryCard(String title, String value, IconData icon) => SizedBox(
    width: 210,
    child: Card(
      color: panel,
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: gold),
            const SizedBox(height: 8),
            Text(
              title,
              style: const TextStyle(color: Colors.white60, fontSize: 12),
            ),
            Text(
              value,
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    ),
  );

  Future<void> editProduct([Product? current]) async {
    final name = TextEditingController(text: current?.name ?? '');
    final price = TextEditingController(
      text: current == null ? '' : current.price.toStringAsFixed(2),
    );
    final icon = TextEditingController(text: current?.icon ?? '🌮');
    String selectedCategory = current?.category ?? 'Tacos';
    final accepted = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (_, refresh) => AlertDialog(
          title: Text(current == null ? 'NUEVO PRODUCTO' : 'EDITAR PRODUCTO'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: name,
                  decoration: const InputDecoration(
                    labelText: 'Nombre',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: price,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Precio',
                    prefixText: '\$ ',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  initialValue: selectedCategory,
                  decoration: const InputDecoration(
                    labelText: 'Categoría',
                    border: OutlineInputBorder(),
                  ),
                  items: ['Tacos', 'Especiales', 'Bebidas', 'Extras']
                      .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                      .toList(),
                  onChanged: (v) =>
                      refresh(() => selectedCategory = v ?? selectedCategory),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: icon,
                  maxLength: 2,
                  decoration: const InputDecoration(
                    labelText: 'Icono o emoji',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('CANCELAR'),
            ),
            FilledButton(
              onPressed: () {
                final value = double.tryParse(price.text.replaceAll(',', '.'));
                if (name.text.trim().isEmpty || value == null || value < 0) {
                  toast('Revisa el nombre y el precio');
                  return;
                }
                Navigator.pop(dialogContext, true);
              },
              child: const Text('GUARDAR'),
            ),
          ],
        ),
      ),
    );
    if (accepted != true) return;
    final updated = Product(
      selectedCategory,
      name.text.trim(),
      double.parse(price.text.replaceAll(',', '.')),
      icon.text.trim().isEmpty ? '•' : icon.text.trim(),
    );
    setState(() {
      if (current == null) {
        productList.add(updated);
      } else {
        productList[productList.indexOf(current)] = updated;
      }
      productList.sort(
        (a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()),
      );
    });
    await saveData();
    toast('Producto guardado');
  }

  Future<void> deleteProduct(Product product) async {
    final confirmed =
        await showDialog<bool>(
          context: context,
          builder: (dialogContext) => AlertDialog(
            title: const Text('QUITAR PRODUCTO'),
            content: Text('¿Deseas quitar “${product.name}” del menú?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext, false),
                child: const Text('CANCELAR'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(dialogContext, true),
                child: const Text('QUITAR'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) return;
    setState(() => productList.remove(product));
    await saveData();
    toast('Producto eliminado');
  }

  Widget settingsPage() => ListView(
    padding: const EdgeInsets.all(16),
    children: [
      const Text(
        'CONFIGURACIÓN DEL NEGOCIO',
        style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
      ),
      const SizedBox(height: 15),
      Card(
        color: panel,
        child: Padding(
          padding: const EdgeInsets.all(15),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Identidad',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: businessController,
                decoration: const InputDecoration(
                  labelText: 'Nombre del negocio',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 10),
              FilledButton(
                onPressed: () {
                  setState(
                    () => businessName = businessController.text.trim().isEmpty
                        ? 'MI NEGOCIO'
                        : businessController.text.trim().toUpperCase(),
                  );
                  saveData();
                  toast('Configuración guardada');
                },
                child: const Text('GUARDAR NOMBRE'),
              ),
            ],
          ),
        ),
      ),
      Card(
        color: panel,
        child: ListTile(
          leading: const Icon(Icons.palette, color: gold),
          title: const Text('Logo y colores'),
          subtitle: const Text('Se habilitará en la siguiente actualización'),
        ),
      ),
      Card(
        color: panel,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      'PRODUCTOS Y PRECIOS',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  FilledButton.icon(
                    onPressed: () => editProduct(),
                    icon: const Icon(Icons.add),
                    label: const Text('AGREGAR'),
                  ),
                ],
              ),
              const Divider(),
              if (productList.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(18),
                  child: Text(
                    'No hay productos. Pulsa AGREGAR para comenzar.',
                    textAlign: TextAlign.center,
                  ),
                ),
              ...productList.map(
                (product) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Text(
                    product.icon,
                    style: const TextStyle(fontSize: 28),
                  ),
                  title: Text(product.name),
                  subtitle: Text(
                    '${product.category} · \$${product.price.toStringAsFixed(2)}',
                  ),
                  onTap: () => editProduct(product),
                  trailing: IconButton(
                    icon: const Icon(
                      Icons.delete_outline,
                      color: Colors.redAccent,
                    ),
                    onPressed: () => deleteProduct(product),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      const Padding(
        padding: EdgeInsets.all(12),
        child: Text(
          'Punto de Venta Express · versión 2.1.0',
          textAlign: TextAlign.center,
          style: TextStyle(color: Colors.white54),
        ),
      ),
    ],
  );
}
