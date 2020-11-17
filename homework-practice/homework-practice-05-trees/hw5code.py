import numpy as np
from collections import Counter
from sklearn.base import BaseEstimator, TransformerMixin

def find_best_split(feature_vector, target_vector):
    """
    Под критерием Джини здесь подразумевается следующая функция:
    $$Q(R) = -\frac {|R_l|}{|R|}H(R_l) -\frac {|R_r|}{|R|}H(R_r)$$,
    $R$ — множество объектов, $R_l$ и $R_r$ — объекты, попавшие в левое и правое поддерево,
     $H(R) = 1-p_1^2-p_0^2$, $p_1$, $p_0$ — доля объектов класса 1 и 0 соответственно.

    Указания:
    * Пороги, приводящие к попаданию в одно из поддеревьев пустого множества объектов, не рассматриваются.
    * В качестве порогов, нужно брать среднее двух сосдених (при сортировке) значений признака
    * Поведение функции в случае константного признака может быть любым.
    * При одинаковых приростах Джини нужно выбирать минимальный сплит.
    * За наличие в функции циклов балл будет снижен. Векторизуйте! :)


    :param feature_vector: вещественнозначный вектор значений признака
    :param target_vector: вектор классов объектов,  len(feature_vector) == len(target_vector)

    :return thresholds: отсортированный по возрастанию вектор со всеми возможными порогами, по которым объекты можно
     разделить на две различные подвыборки, или поддерева
    :return ginis: вектор со значениями критерия Джини для каждого из порогов в thresholds len(ginis) == len(thresholds)
    :return threshold_best: оптимальный порог (число)
    :return gini_best: оптимальное значение критерия Джини (число)
    """
    feature_vector = np.array(feature_vector)
    target_vector = np.array(target_vector)
    
    n = feature_vector.size
    perm = np.argsort(feature_vector)
    
    sorted_feature_vector = feature_vector[perm]
    thresholds_row = (sorted_feature_vector[0:-1] + sorted_feature_vector[1:])
    thresholds, thresholds_indicis = np.unique(thresholds_row[::-1], return_index=True)
    thresholds_indicis = np.sort(- thresholds_indicis + (n - 2))
    thresholds_indicis = thresholds_indicis[feature_vector[perm][thresholds_indicis] != feature_vector[perm][thresholds_indicis + 1]]
    thresholds = thresholds_row[thresholds_indicis]
    thresholds = thresholds / 2
   
    sorted_target_vector = target_vector[perm]
    pref1 = np.cumsum(sorted_target_vector)[:-1]
    pref0 = np.cumsum(np.ones(n) - sorted_target_vector)[:-1]
    suff1 = - pref1 + np.sum(target_vector[perm])
    suff0 = - pref0 + (n - np.sum(target_vector[perm]))
    R_l_size = np.arange(1, n, 1)
    R_r_size = - R_l_size + n
    
    ginis = \
        - 1.0 * R_l_size / n * (np.ones(n - 1) - (pref1 / R_l_size) ** 2 - (pref0 / R_l_size) ** 2) \
        - 1.0 * R_r_size / n * (np.ones(n - 1) - (suff1 / R_r_size) ** 2 - (suff0 / R_r_size) ** 2)
    ginis = ginis[thresholds_indicis]
    best = np.argmax(ginis)
    threshold_best = thresholds[best]
    gini_best = ginis[best]
    
    return (thresholds, ginis, threshold_best, gini_best)


class DecisionTree(BaseEstimator, TransformerMixin):
    def __init__(self, feature_types, max_depth=None, min_samples_split=None, min_samples_leaf=None):
        if np.any(list(map(lambda x: x != "real" and x != "categorical", feature_types))):
            raise ValueError("There is unknown feature type")

        self._tree = {}
        self._feature_types = feature_types
        self._max_depth = max_depth
        self._min_samples_split = min_samples_split
        self._min_samples_leaf = min_samples_leaf

    def _fit_node(self, sub_X, sub_y, node, cur_depth=0):
        if np.all(sub_y == sub_y[0]) or (not self._max_depth is None and cur_depth >= self._max_depth):
            node["type"] = "terminal"
            node["class"] = sub_y[0]
            return

        feature_best, threshold_best, gini_best, split = None, None, None, None
        for feature in range(sub_X.shape[1]):
            feature_type = self._feature_types[feature]
            categories_map = {}

            if feature_type == "real":
                feature_vector = sub_X[:, feature]
            elif feature_type == "categorical":
                counts = Counter(sub_X[:, feature])
                clicks = Counter(sub_X[sub_y == 1, feature])
                ratio = {}
                for key, current_count in counts.items():
                    if key in clicks:
                        current_click = clicks[key]
                    else:
                        current_click = 0
                    ratio[key] = current_click / current_count 
                sorted_categories = list(map(lambda x: x[0], sorted(ratio.items(), key=lambda x: x[1])))
                categories_map = dict(zip(sorted_categories, list(range(len(sorted_categories)))))
                feature_vector = np.fromiter(map(lambda x: categories_map[x], sub_X[:, feature]), dtype=int)
            else:
                raise ValueError
            
            if len(np.unique(feature_vector)) == 1:
                continue
            
            _, _, threshold, gini = find_best_split(feature_vector, sub_y)
            if gini_best is None or gini > gini_best:
                if (feature_vector < threshold).sum() == sub_X.shape[0] or (feature_vector < threshold).sum() == 0:
                    continue
                    
                feature_best = feature
                gini_best = gini
                split = feature_vector < threshold

                if feature_type == "real":
                    threshold_best = threshold
                elif feature_type == "categorical":
                    threshold_best = list(map(lambda x: x[0],
                                              filter(lambda x: x[1] < threshold, categories_map.items())))
                else:
                    raise ValueError
           
        if feature_best is None:
            node["type"] = "terminal"
            node["class"] = Counter(sub_y).most_common(1)[0][0]
            return

        node["type"] = "nonterminal"

        node["feature_split"] = feature_best
        if self._feature_types[feature_best] == "real":
            node["threshold"] = threshold_best
        elif self._feature_types[feature_best] == "categorical":
            node["categories_split"] = threshold_best
        else:
            raise ValueError
        node["left_child"], node["right_child"] = {}, {}
        self._fit_node(sub_X[split], sub_y[split], node["left_child"], cur_depth + 1)
        self._fit_node(sub_X[np.logical_not(split)], sub_y[np.logical_not(split)], node["right_child"], cur_depth + 1)

    def _predict_node(self, x, node):
        if node["type"] == "terminal":
            return node["class"]
        
        feature = node["feature_split"]
        if self._feature_types[feature] == "real":
            direction = "left_child" if x[feature] < node["threshold"] else "right_child"
        else:
            direction = "left_child" if x[feature] in node["categories_split"] else "right_child"
        return self._predict_node(x, node[direction])

    def fit(self, X, y):
        if np.any(list(map(lambda x: x != 0 and x != 1, y))):
            while True:
                pass

        self._fit_node(X, y, self._tree)
        return self

    def predict(self, X):
        predicted = []
        for x in X:
            predicted.append(self._predict_node(x, self._tree))
        return np.array(predicted)
    
    def get_params(self, deep=False):
        return {'feature_types':self._feature_types}
