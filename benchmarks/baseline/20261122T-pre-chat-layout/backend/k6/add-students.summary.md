# k6 summary

scenario: add_students

- vus: min=1.000, max=1.000
- http_req_connecting: max=0.074, p(90)=0.007, p(95)=0.041, p(99)=0.067, avg=0.007, min=0.000, med=0.000
- http_req_duration{expected_response:true}: p(90)=15.986, p(95)=16.954, p(99)=17.729, avg=11.643, min=5.328, med=10.866, max=17.923
- http_req_blocked: min=0.004, med=0.011, max=0.102, p(90)=0.027, p(95)=0.065, p(99)=0.095, avg=0.020
- http_req_receiving: med=0.074, max=0.105, p(90)=0.089, p(95)=0.097, p(99)=0.103, avg=0.066, min=0.026
- http_req_duration: p(95)=16.954, p(99)=17.729, avg=11.643, min=5.328, med=10.866, max=17.923, p(90)=15.986
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- iterations: count=10.000, rate=4.702
- http_req_sending: p(99)=0.122, avg=0.057, min=0.020, med=0.053, max=0.127, p(90)=0.075, p(95)=0.101
- http_req_waiting: p(95)=16.791, p(99)=17.587, avg=11.520, min=5.257, med=10.748, max=17.786, p(90)=15.796
- http_req_failed: rate=0.000
