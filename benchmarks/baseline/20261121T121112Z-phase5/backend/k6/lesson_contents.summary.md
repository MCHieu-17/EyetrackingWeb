# k6 summary

scenario: lesson_contents

- http_req_blocked: med=0.011, max=0.162, p(90)=0.014, p(95)=0.015, p(99)=0.153, avg=0.013, min=0.002
- http_req_receiving: med=0.074, max=0.396, p(90)=0.267, p(95)=0.304, p(99)=0.355, avg=0.118, min=0.025
- iterations: count=230.000, rate=22.763
- vus: min=5.000, max=5.000
- http_req_duration{expected_response:true}: med=18.436, max=33.399, p(90)=25.246, p(95)=27.676, p(99)=30.656, avg=17.629, min=4.770
- http_req_sending: p(99)=0.083, avg=0.038, min=0.008, med=0.040, max=0.092, p(90)=0.052, p(95)=0.062
- http_req_failed: rate=0.000
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_connecting: max=0.119, p(90)=0.000, p(95)=0.000, p(99)=0.112, avg=0.002, min=0.000, med=0.000
- http_req_duration: p(95)=27.676, p(99)=30.656, avg=17.629, min=4.770, med=18.436, max=33.399, p(90)=25.246
- http_req_waiting: med=18.294, max=33.282, p(90)=25.069, p(95)=27.333, p(99)=30.460, avg=17.472, min=4.727
